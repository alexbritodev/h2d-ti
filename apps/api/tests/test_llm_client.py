import json
from decimal import Decimal

import httpx
import pytest

from h2d.llm.client import (
    ChatMessage,
    FakeLLM,
    LLMError,
    OpenRouterClient,
    UnavailableLLM,
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
