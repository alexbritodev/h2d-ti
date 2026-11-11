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


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        fallbacks: list[str],
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self.model_name = model
        self._fallbacks = fallbacks
        self._timeout = timeout
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
        # Modelos que raciocinam gastam todo o max_tokens pensando e devolvem texto vazio ("effort:
        # low" não basta: medido, 1500 de 1500 tokens). Desligar o raciocínio faz responder.
        body["reasoning"] = {"enabled": False}
        if self._fallbacks:
            # O OpenRouter tenta os modelos da lista, em ordem, se o primeiro falhar.
            body["models"] = [self.model_name, *self._fallbacks]
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "X-Title": "H2D - TI",
        }
        started = time.monotonic()
        last_error = "sem resposta"
        rate_limited = False
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            for attempt in range(5):
                try:
                    response = await client.post(OPENROUTER_URL, json=body, headers=headers)
                except httpx.HTTPError as error:
                    last_error = f"{type(error).__name__}: {error}"
                else:
                    if response.status_code == 200:
                        try:
                            return self._parse(response, started)
                        except EmptyAnswerError as error:
                            # O roteador gratuito sorteia o modelo a cada chamada: tenta de novo,
                            # com mais espaço para o raciocínio caber e sobrar para a resposta.
                            last_error = str(error)
                            body["max_tokens"] = min(int(body["max_tokens"]) * 2, 4000)
                            continue
                    rate_limited = response.status_code == 429
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    if response.status_code == 400 and self._relax_reasoning(body, response.text):
                        continue  # o modelo não aceita desligar o raciocínio: tenta o modo leve
                    if response.status_code not in RETRYABLE:
                        break
                if attempt < 4:
                    await self._sleep(1.5 * (attempt + 1))
        raise LLMError(last_error, rate_limited=rate_limited)

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
        raise LLMError("OPENROUTER_API_KEY não está configurada")


@lru_cache
def get_llm() -> LLM:
    settings = get_settings()
    if settings.openrouter_api_key is None or not settings.openrouter_api_key.get_secret_value():
        return UnavailableLLM()
    fallbacks = [m.strip() for m in settings.openrouter_fallback_models.split(",") if m.strip()]
    return OpenRouterClient(
        settings.openrouter_api_key.get_secret_value(),
        model=settings.openrouter_model,
        fallbacks=fallbacks,
        timeout=settings.llm_timeout_seconds,
    )


def parse_json_object(text: str) -> dict[str, Any]:
    """Extrai o primeiro objeto JSON de uma resposta (o modelo às vezes cerca com texto)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("a resposta não traz um objeto JSON")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("a resposta não é um objeto JSON")
    return value
