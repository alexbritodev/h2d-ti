import json
from decimal import Decimal

import httpx
import pytest

from h2d.config import get_settings
from h2d.llm.client import (
    ChatMessage,
    FakeLLM,
    GeminiClient,
    LLMError,
    OpenRouterClient,
    UnavailableLLM,
    get_llm,
    parse_json_object,
)

MENSAGENS = [ChatMessage("user", "olá")]


async def _sem_espera(_: float) -> None:
    return None


def _client(handler, fallbacks=None) -> OpenRouterClient:
    return OpenRouterClient(
        "chave-de-teste",
        model="a/modelo:free",
        fallbacks=fallbacks or [],
        timeout=5,
        transport=httpx.MockTransport(handler),
        sleep=_sem_espera,
    )


def _ok(text="oi", cost=0.0021):
    return httpx.Response(
        200,
        json={
            "model": "a/modelo:free",
            "choices": [{"message": {"content": f" {text} "}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 5, "cost": cost},
        },
    )


async def test_resposta_traz_texto_tokens_e_custo():
    resultado = await _client(lambda request: _ok("resposta")).complete(MENSAGENS)

    assert resultado.text == "resposta"
    assert (resultado.input_tokens, resultado.output_tokens) == (12, 5)
    assert resultado.cost_usd == Decimal("0.0021")


async def test_envia_chave_modelo_e_lista_de_reserva():
    vistos = {}

    def handler(request: httpx.Request) -> httpx.Response:
        vistos["auth"] = request.headers["authorization"]
        vistos["body"] = json.loads(request.content)
        return _ok()

    await _client(handler, fallbacks=["b/reserva:free"]).complete(MENSAGENS, temperature=0.0)

    assert vistos["auth"] == "Bearer chave-de-teste"
    assert vistos["body"]["models"] == ["a/modelo:free", "b/reserva:free"]
    assert vistos["body"]["temperature"] == 0.0


async def test_desliga_o_raciocinio_para_o_modelo_responder():
    vistos = {}

    def handler(request: httpx.Request) -> httpx.Response:
        vistos["body"] = json.loads(request.content)
        return _ok()

    await _client(handler).complete(MENSAGENS)

    assert vistos["body"]["reasoning"] == {"enabled": False}


async def test_modelo_com_raciocinio_obrigatorio_cai_para_esforco_baixo_e_depois_sem_parametro():
    corpos = []

    def handler(request: httpx.Request) -> httpx.Response:
        corpos.append(json.loads(request.content).get("reasoning", "ausente"))
        if len(corpos) < 3:
            return httpx.Response(400, text='{"error":"Reasoning is mandatory for this model"}')
        return _ok("respondeu")

    resultado = await _client(handler).complete(MENSAGENS)

    assert resultado.text == "respondeu"
    assert corpos == [{"enabled": False}, {"effort": "low"}, "ausente"]


async def test_texto_vazio_por_falta_de_tokens_tenta_de_novo_com_mais_espaco():
    limites = []

    def handler(request: httpx.Request) -> httpx.Response:
        limites.append(json.loads(request.content)["max_tokens"])
        if len(limites) == 1:
            return httpx.Response(
                200,
                json={
                    "model": "a/modelo:free",
                    "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                    "usage": {"completion_tokens": 700},
                },
            )
        return _ok("agora sim")

    resultado = await _client(handler).complete(MENSAGENS, max_tokens=700)

    assert resultado.text == "agora sim"
    assert limites == [700, 1400]


async def test_texto_vazio_sempre_vira_erro_e_nao_resposta_vazia():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "a/modelo:free",
                "choices": [{"message": {"content": None}, "finish_reason": "length"}],
                "usage": {"completion_tokens": 1500},
            },
        )

    with pytest.raises(LLMError, match="gastou todos os tokens"):
        await _client(handler).complete(MENSAGENS)


async def test_tenta_de_novo_em_erro_temporario():
    tentativas = []

    def handler(request: httpx.Request) -> httpx.Response:
        tentativas.append(1)
        return httpx.Response(503, text="fora") if len(tentativas) < 3 else _ok("voltou")

    resultado = await _client(handler).complete(MENSAGENS)

    assert resultado.text == "voltou"
    assert len(tentativas) == 3


async def test_limite_de_requisicoes_vira_erro_marcado():
    cliente = _client(lambda request: httpx.Response(429, text="limite"))

    with pytest.raises(LLMError) as erro:
        await cliente.complete(MENSAGENS)

    assert erro.value.rate_limited is True


async def test_erro_definitivo_nao_repete():
    tentativas = []

    def handler(request: httpx.Request) -> httpx.Response:
        tentativas.append(1)
        return httpx.Response(401, text="chave inválida")

    with pytest.raises(LLMError, match="401"):
        await _client(handler).complete(MENSAGENS)

    assert len(tentativas) == 1


async def test_resposta_sem_o_formato_esperado_e_erro():
    cliente = _client(lambda request: httpx.Response(200, json={"choices": []}))

    with pytest.raises(LLMError, match="inesperada"):
        await cliente.complete(MENSAGENS)


async def test_falha_de_rede_vira_erro():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    with pytest.raises(LLMError, match="ConnectError"):
        await _client(handler).complete(MENSAGENS)


async def test_fake_registra_as_chamadas_e_responde_pela_funcao():
    fake = FakeLLM(lambda messages: "ok: " + messages[-1].content)

    resultado = await fake.complete(MENSAGENS)

    assert resultado.text == "ok: olá"
    assert len(fake.calls) == 1


async def test_sem_chave_o_pedido_falha_com_motivo():
    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        await UnavailableLLM().complete(MENSAGENS)


def test_json_dentro_de_texto_e_extraido():
    assert parse_json_object('Claro!\n{"a": 1, "b": "x"}\nfim') == {"a": 1, "b": "x"}
    with pytest.raises(ValueError):
        parse_json_object("sem json aqui")


def _gemini_client(handler, model: str = "gemini-3.8-flash") -> GeminiClient:
    return GeminiClient(
        "AIza-teste",
        model=model,
        timeout=5,
        transport=httpx.MockTransport(handler),
        sleep=_sem_espera,
    )


def _gemini_ok(text: str = "oi"):
    return httpx.Response(
        200,
        json={
            "modelVersion": "gemini-3.8-flash",
            "candidates": [{"content": {"parts": [{"text": f" {text} "}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 15, "candidatesTokenCount": 6},
        },
    )


async def test_gemini_envia_system_instruction_thinking_e_extrai_tokens():
    vistos = {}

    def handler(request: httpx.Request) -> httpx.Response:
        vistos["url"] = str(request.url)
        vistos["key"] = request.headers["x-goog-api-key"]
        vistos["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "modelVersion": "gemini-3.8-flash",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "raciocinio oculto", "thought": True},
                                {"text": " resposta final "},
                            ]
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 15, "candidatesTokenCount": 6},
            },
        )

    cliente = _gemini_client(handler, model="google/gemini-3.8-flash")
    resultado = await cliente.complete(
        [
            ChatMessage("system", "seja breve"),
            ChatMessage("user", "oi"),
            ChatMessage("user", "tudo bem?"),
        ]
    )

    assert vistos["url"].endswith("/v1beta/models/gemini-3.8-flash:generateContent")
    assert vistos["key"] == "AIza-teste"
    assert vistos["body"]["systemInstruction"] == {"parts": [{"text": "seja breve"}]}
    assert vistos["body"]["contents"] == [
        {"role": "user", "parts": [{"text": "oi"}, {"text": "tudo bem?"}]}
    ]
    assert vistos["body"]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert resultado.text == "resposta final"
    assert (resultado.input_tokens, resultado.output_tokens) == (15, 6)
    assert resultado.cost_usd == Decimal(0)
    assert resultado.model == "gemini-3.8-flash"


async def test_gemini_remove_thinking_config_em_erro_400():
    configs = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        configs.append("thinkingConfig" in body["generationConfig"])
        if len(configs) == 1:
            return httpx.Response(
                400, text='{"error":{"message":"Request contains an invalid argument."}}'
            )
        return _gemini_ok("respondeu")

    resultado = await _gemini_client(handler, model="3.1-flash-lite").complete(MENSAGENS)

    assert resultado.text == "respondeu"
    assert configs == [True, False]


async def test_gemini_texto_vazio_em_max_tokens_tenta_de_novo_com_mais_espaco():
    limites = []

    def handler(request: httpx.Request) -> httpx.Response:
        limites.append(json.loads(request.content)["generationConfig"]["maxOutputTokens"])
        if len(limites) == 1:
            return httpx.Response(
                200,
                json={
                    "modelVersion": "gemini-3.8-flash",
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "pensando", "thought": True}]},
                            "finishReason": "MAX_TOKENS",
                        }
                    ],
                },
            )
        return _gemini_ok("agora sim")

    resultado = await _gemini_client(handler).complete(MENSAGENS, max_tokens=700)

    assert resultado.text == "agora sim"
    assert limites == [700, 1400]


def test_get_llm_usa_gemini_quando_gemini_api_key_definida(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-chave-teste")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    get_settings.cache_clear()
    get_llm.cache_clear()
    try:
        llm = get_llm()
        assert isinstance(llm, GeminiClient)
        assert llm.model_name == "gemini-3.8-flash"
    finally:
        get_settings.cache_clear()
        get_llm.cache_clear()


async def test_gemini_usa_modelo_de_reserva_em_503_ou_404():
    modelos = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        modelos.append(url.rsplit("/", 1)[-1].split(":")[0])
        if "gemini-4-hydrogen" in url:
            return httpx.Response(503, text='{"error":{"code":503,"status":"UNAVAILABLE"}}')
        return _gemini_ok("ok do reserva")

    cliente = GeminiClient(
        "AIza-teste",
        model="gemini-4-hydrogen",
        fallbacks=["gemini-3.1-flash-lite"],
        timeout=5,
        transport=httpx.MockTransport(handler),
        sleep=_sem_espera,
    )
    resultado = await cliente.complete(MENSAGENS)

    assert resultado.text == "ok do reserva"
    assert modelos == ["gemini-4-hydrogen", "gemini-4-hydrogen", "gemini-3.1-flash-lite"]


async def test_gemini_resposta_cortada_por_max_tokens_tenta_com_mais_espaco():
    limites = []

    def handler(request: httpx.Request) -> httpx.Response:
        limites.append(json.loads(request.content)["generationConfig"]["maxOutputTokens"])
        if len(limites) == 1:
            return httpx.Response(
                200,
                json={
                    "modelVersion": "gemini-3.1-flash-lite",
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "Para criar um"}]},
                            "finishReason": "MAX_TOKENS",
                        }
                    ],
                },
            )
        return _gemini_ok("Para criar um usuário, use useradd.")

    resultado = await _gemini_client(handler).complete(MENSAGENS, max_tokens=700)

    assert resultado.text == "Para criar um usuário, use useradd."
    assert limites == [700, 1400]


async def test_cliente_local_ollama_sem_chave_e_sem_campos_openrouter():
    vistos = {}

    def handler(request: httpx.Request) -> httpx.Response:
        vistos["url"] = str(request.url)
        vistos["auth"] = request.headers.get("authorization")
        vistos["body"] = json.loads(request.content)
        return _ok("gemma4 ok", cost=0)

    cliente = OpenRouterClient(
        "",
        model="gemma4",
        fallbacks=[],
        timeout=10,
        base_url="http://host.docker.internal:11434/v1",
        transport=httpx.MockTransport(handler),
        sleep=_sem_espera,
    )
    resultado = await cliente.complete(MENSAGENS)

    assert resultado.text == "gemma4 ok"
    assert vistos["url"] == "http://host.docker.internal:11434/v1/chat/completions"
    assert vistos["auth"] is None
    assert "reasoning" not in vistos["body"]
    assert "models" not in vistos["body"]


def test_get_llm_usa_servidor_local_quando_llm_base_url_definida(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://host.docker.internal:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "gemma4")
    get_settings.cache_clear()
    get_llm.cache_clear()
    try:
        llm = get_llm()
        assert isinstance(llm, OpenRouterClient)
        assert llm.model_name == "gemma4"
        assert llm._url == "http://host.docker.internal:11434/v1/chat/completions"
    finally:
        get_settings.cache_clear()
        get_llm.cache_clear()
