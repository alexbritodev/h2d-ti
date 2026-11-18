"""Cliente do modelo de linguagem: OpenRouter em produção, `FakeLLM` nos testes.

O resto do sistema só conhece o protocolo `LLM`. Cada chamada devolve tokens e custo, e quem chama
grava a linha em `llm_calls`.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Any, Protocol

import httpx

from h2d.config import get_settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
RETRYABLE = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system", "user" ou "assistant"
    content: str


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    latency_ms: int = 0


class LLMError(Exception):
    """Falha ao falar com o modelo. A mensagem é técnica: o usuário recebe um texto próprio."""

    def __init__(self, message: str, *, rate_limited: bool = False) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited


class EmptyAnswerError(LLMError):
    """O modelo gastou todo o limite de tokens raciocinando e não escreveu a resposta."""


class LLM(Protocol):
    model_name: str

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> LLMResult: ...


async def _post_with_retries(
    *,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    request_timeout: float,
    transport: httpx.AsyncBaseTransport | None,
    sleep: Callable[[float], Awaitable[None]],
    parse: Callable[[httpx.Response, float], LLMResult],
    on_empty_answer: Callable[[dict[str, Any]], None],
    on_bad_request: Callable[[dict[str, Any], str], bool],
    max_attempts: int = 5,
) -> LLMResult:
    """Executa chamada HTTP POST com retentativas para falhas transitórias e limites de resposta."""
    started = time.monotonic()
    last_error = "sem resposta"
    rate_limited = False
    async with httpx.AsyncClient(timeout=request_timeout, transport=transport) as client:
        for attempt in range(max_attempts):
            try:
                response = await client.post(url, json=body, headers=headers)
            except httpx.HTTPError as error:
                last_error = f"{type(error).__name__}: {error}"
            else:
                if response.status_code == 200:
                    try:
                        return parse(response, started)
                    except EmptyAnswerError as error:
                        # Tenta novamente com mais espaço para o raciocínio e a resposta.
                        last_error = str(error)
                        on_empty_answer(body)
                        continue
                rate_limited = response.status_code == 429
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                if response.status_code == 400 and on_bad_request(body, response.text):
                    continue
                if response.status_code not in RETRYABLE:
                    break
            if attempt < max_attempts - 1:
                await sleep(1.5 * (attempt + 1))
    raise LLMError(last_error, rate_limited=rate_limited)


def _normalize_chat_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if not cleaned:
        return OPENROUTER_URL
    if cleaned.endswith("/chat/completions"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
    return f"{cleaned}/v1/chat/completions"


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        fallbacks: list[str],
        timeout: float,
        base_url: str = OPENROUTER_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key.strip()
        self.model_name = model
        self._fallbacks = fallbacks
        self._timeout = timeout
        self._url = _normalize_chat_url(base_url)
        self._is_openrouter = self._url == OPENROUTER_URL
        self._transport = transport
        self._sleep = sleep

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> LLMResult:
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if self._is_openrouter:
            # Modelos que raciocinam gastam todo o max_tokens pensando e devolvem texto vazio.
            body["reasoning"] = {"enabled": False}
            if self._fallbacks:
                # O OpenRouter tenta os modelos da lista, em ordem, se o primeiro falhar.
                body["models"] = [self.model_name, *self._fallbacks]
            headers["X-Title"] = "H2D - TI"
        return await _post_with_retries(
            url=self._url,
            body=body,
            headers=headers,
            request_timeout=self._timeout,
            transport=self._transport,
            sleep=self._sleep,
            parse=self._parse,
            on_empty_answer=self._expand_max_tokens,
            on_bad_request=self._relax_reasoning if self._is_openrouter else (lambda _b, _t: False),
            max_attempts=5 if self._is_openrouter else 2,
        )

    @staticmethod
    def _expand_max_tokens(body: dict[str, Any]) -> None:
        body["max_tokens"] = min(int(body["max_tokens"]) * 2, 4000)

    @staticmethod
    def _relax_reasoning(body: dict[str, Any], error_text: str) -> bool:
        """Modelos com raciocínio obrigatório recusam `enabled: false`: desce para esforço baixo e,
        se ainda recusar, tira o parâmetro. Devolve False quando não há mais o que afrouxar."""
        if "reasoning" not in error_text.lower() or "reasoning" not in body:
            return False
        if body["reasoning"] == {"enabled": False}:
            body["reasoning"] = {"effort": "low"}
        else:
            del body["reasoning"]
        return True

    def _parse(self, response: httpx.Response, started: float) -> LLMResult:
        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMError(f"Resposta inesperada do provedor: {error}") from error
        if not text.strip() and choice.get("finish_reason") == "length":
            # Sem isto o texto vazio parecia "o modelo não achou" e o usuário recebia a pergunta
            # de esclarecimento no lugar da resposta.
            raise EmptyAnswerError(
                "O modelo gastou todos os tokens raciocinando e não escreveu a resposta"
            )
        usage = data.get("usage") or {}
        return LLMResult(
            text=text.strip(),
            model=str(data.get("model") or self.model_name),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            cost_usd=Decimal(str(usage.get("cost") or 0)),
            latency_ms=int((time.monotonic() - started) * 1000),
        )


class GeminiClient:
    """Cliente da API direta do Google AI Studio (Gemini)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.1-flash-lite",
        fallbacks: list[str] | None = None,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self.model_name = self._normalize_model(model)
        seen = {self.model_name}
        self._fallbacks: list[str] = []
        for fb in fallbacks or []:
            norm = self._normalize_model(fb)
            if norm not in seen:
                seen.add(norm)
                self._fallbacks.append(norm)
        self._timeout = timeout
        self._transport = transport
        self._sleep = sleep

    @staticmethod
    def _normalize_model(model: str) -> str:
        normalized = model.strip()
        for prefix in ("google/", "models/"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
        if not normalized or normalized == "openrouter/free":
            return "gemini-3.1-flash-lite"
        if normalized[0].isdigit():
            normalized = f"gemini-{normalized}"
        return normalized

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> LLMResult:
        system_parts = [{"text": m.content} for m in messages if m.role == "system"]
        contents: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                continue
            role = "model" if message.role == "assistant" else "user"
            part = {"text": message.content}
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": role, "parts": [part]})
        if not contents:
            contents.append({"role": "user", "parts": [{"text": ""}]})

        candidates = [self.model_name, *self._fallbacks]
        last_error: LLMError | None = None
        for idx, current_model in enumerate(candidates):
            has_more = idx < len(candidates) - 1
            body: dict[str, Any] = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
            if system_parts:
                body["systemInstruction"] = {"parts": system_parts}
            try:
                return await self._complete_single_model(
                    current_model,
                    body,
                    has_fallback=has_more,
                )
            except LLMError as error:
                last_error = error
                if not has_more:
                    raise
        raise last_error or LLMError("sem resposta")

    async def _complete_single_model(
        self,
        model_name: str,
        body: dict[str, Any],
        *,
        has_fallback: bool,
    ) -> LLMResult:
        url = f"{GEMINI_BASE_URL}/{model_name}:generateContent"
        headers = {"x-goog-api-key": self._api_key}
        per_attempt_timeout = min(self._timeout, 25.0) if self._fallbacks else self._timeout
        max_attempts = 2 if has_fallback else 5
        started = time.monotonic()
        last_error = "sem resposta"
        rate_limited = False

        async with httpx.AsyncClient(
            timeout=per_attempt_timeout, transport=self._transport
        ) as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.post(url, json=body, headers=headers)
                except httpx.TimeoutException as error:
                    last_error = f"{type(error).__name__}: {error}"
                    if has_fallback:
                        break
                except httpx.HTTPError as error:
                    last_error = f"{type(error).__name__}: {error}"
                else:
                    if response.status_code == 200:
                        try:
                            current_max = int(body["generationConfig"]["maxOutputTokens"])
                            return self._parse(
                                response,
                                started,
                                fallback_model=model_name,
                                allow_truncated=current_max >= 4000,
                            )
                        except EmptyAnswerError as error:
                            last_error = str(error)
                            self._expand_max_tokens(body)
                            continue
                    rate_limited = response.status_code == 429
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    if response.status_code == 400 and self._relax_thinking(body, response.text):
                        continue
                    if response.status_code == 404 and has_fallback:
                        break
                    if response.status_code not in RETRYABLE:
                        break
                if attempt < max_attempts - 1:
                    await self._sleep(1.5 * (attempt + 1))
        raise LLMError(last_error, rate_limited=rate_limited)

    @staticmethod
    def _expand_max_tokens(body: dict[str, Any]) -> None:
        config = body["generationConfig"]
        config["maxOutputTokens"] = min(int(config["maxOutputTokens"]) * 2, 4000)

    @staticmethod
    def _relax_thinking(body: dict[str, Any], _error_text: str) -> bool:
        config = body.get("generationConfig", {})
        if "thinkingConfig" not in config:
            return False
        del config["thinkingConfig"]
        return True

    def _parse(
        self,
        response: httpx.Response,
        started: float,
        *,
        fallback_model: str | None = None,
        allow_truncated: bool = True,
    ) -> LLMResult:
        try:
            data = response.json()
            candidate = data["candidates"][0]
            parts = (candidate.get("content") or {}).get("parts") or []
            text = "".join(
                str(part.get("text") or "")
                for part in parts
                if isinstance(part, dict) and not part.get("thought")
            )
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMError(f"Resposta inesperada do provedor: {error}") from error
        if candidate.get("finishReason") in ("MAX_TOKENS", "length"):
            if not text.strip():
                raise EmptyAnswerError(
                    "O modelo gastou todos os tokens raciocinando e não escreveu a resposta"
                )
            if not allow_truncated:
                raise EmptyAnswerError("A resposta foi cortada pelo limite de tokens")
        usage = data.get("usageMetadata") or {}
        return LLMResult(
            text=text.strip(),
            model=str(data.get("modelVersion") or fallback_model or self.model_name),
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0),
            cost_usd=Decimal(0),
            latency_ms=int((time.monotonic() - started) * 1000),
        )


Handler = Callable[[list[ChatMessage]], str]


class FakeLLM:
    """Modelo de mentira para testes: responde com a função recebida, sem rede e sem custo."""

    model_name = "fake/llm"

    def __init__(self, handler: Handler | None = None) -> None:
        self._handler = handler or (lambda messages: messages[-1].content)
        self.calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> LLMResult:
        self.calls.append(messages)
        text = self._handler(messages)
        words = len(text.split())
        return LLMResult(
            text=text,
            model=self.model_name,
            input_tokens=sum(len(m.content.split()) for m in messages),
            output_tokens=words,
        )


class UnavailableLLM:
    """Usado quando não há chave configurada: todo pedido falha com um motivo claro."""

    model_name = "indisponivel"

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> LLMResult:
        raise LLMError("GEMINI_API_KEY (ou OPENROUTER_API_KEY) não está configurada")


@lru_cache
def get_llm() -> LLM:
    settings = get_settings()
    deepseek_key = (
        settings.deepseek_api_key.get_secret_value().strip() if settings.deepseek_api_key else ""
    )
    if deepseek_key:
        return OpenRouterClient(
            deepseek_key,
            model=settings.deepseek_model,
            fallbacks=[],
            timeout=settings.llm_timeout_seconds,
            base_url=DEEPSEEK_URL,
        )
    local_url = settings.llm_base_url.strip()
    if local_url:
        local_key = settings.llm_api_key.get_secret_value().strip() if settings.llm_api_key else ""
        return OpenRouterClient(
            local_key,
            model=settings.llm_model,
            fallbacks=[],
            timeout=settings.llm_timeout_seconds,
            base_url=local_url,
        )
    gemini_key = (
        settings.gemini_api_key.get_secret_value().strip() if settings.gemini_api_key else ""
    )
    gemini_fallbacks = [m.strip() for m in settings.gemini_fallback_models.split(",") if m.strip()]
    if gemini_key:
        return GeminiClient(
            gemini_key,
            model=settings.gemini_model,
            fallbacks=gemini_fallbacks,
            timeout=settings.llm_timeout_seconds,
        )
    openrouter_key = (
        settings.openrouter_api_key.get_secret_value().strip()
        if settings.openrouter_api_key
        else ""
    )
    if openrouter_key.startswith(("AIza", "AQ.")):
        model = (
            settings.gemini_model
            if settings.openrouter_model in ("", "openrouter/free")
            else settings.openrouter_model
        )
        return GeminiClient(
            openrouter_key,
            model=model,
            fallbacks=gemini_fallbacks,
            timeout=settings.llm_timeout_seconds,
        )
    if openrouter_key:
        fallbacks = [m.strip() for m in settings.openrouter_fallback_models.split(",") if m.strip()]
        return OpenRouterClient(
            openrouter_key,
            model=settings.openrouter_model,
            fallbacks=fallbacks,
            timeout=settings.llm_timeout_seconds,
        )
    return UnavailableLLM()


def parse_json_object(text: str) -> dict[str, Any]:
    """Extrai o primeiro objeto JSON de uma resposta (o modelo às vezes cerca com texto)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("a resposta não traz um objeto JSON")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("a resposta não é um objeto JSON")
    return value
