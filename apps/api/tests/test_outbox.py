import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.models import OutboxEvent, OutboxStatus
from h2d.outbox import MAX_ATTEMPTS, deliver_pending, sign, verify

SEGREDO = "segredo-compartilhado-de-teste"
URL = "http://n8n:5678/webhook/h2d-events"
AGORA = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _evento(session: AsyncSession, **kw) -> OutboxEvent:
    # Já vencido em relação ao "agora" fixo dos testes (o padrão do banco é o relógio real).
    kw.setdefault("next_attempt_at", AGORA - timedelta(minutes=1))
    event = OutboxEvent(type="ticket.created", payload={"code": "H2D-0001"}, **kw)
    session.add(event)
    await session.flush()
    return event


def test_assinatura_confere_e_barra_corpo_alterado_horario_velho_e_segredo_errado():
    corpo = b'{"a":1}'
    ts = str(int(AGORA.timestamp()))
    assinatura = sign(SEGREDO, ts, corpo)

    assert verify(SEGREDO, ts, corpo, assinatura, now=AGORA)
    assert not verify(SEGREDO, ts, b'{"a":2}', assinatura, now=AGORA)
    assert not verify("outro-segredo", ts, corpo, assinatura, now=AGORA)
    assert not verify(SEGREDO, ts, corpo, assinatura, now=AGORA + timedelta(minutes=6))
    assert not verify(SEGREDO, "nao-e-numero", corpo, assinatura, now=AGORA)
    assert not verify(SEGREDO, ts, corpo, "", now=AGORA)


async def test_entrega_assinada_marca_como_entregue(session):
    event = await _evento(session)
    vistos = {}

    def handler(request: httpx.Request) -> httpx.Response:
        vistos["headers"] = request.headers
        vistos["body"] = request.content
        return httpx.Response(200)

    async with _client(handler) as client:
        tentados = await deliver_pending(session, client, url=URL, secret=SEGREDO, now=AGORA)

    assert tentados == 1
    await session.refresh(event)
    assert event.status is OutboxStatus.DELIVERED and event.delivered_at == AGORA
    headers = vistos["headers"]
    assert headers["x-h2d-event-id"] == str(event.event_id)
    assert headers["x-h2d-event-type"] == "ticket.created"
    # Quem recebe consegue conferir a assinatura com o mesmo segredo.
    assert verify(
        SEGREDO, headers["x-h2d-timestamp"], vistos["body"], headers["x-h2d-signature"], now=AGORA
    )
    assert json.loads(vistos["body"])["event_id"] == str(event.event_id)


async def test_falha_espera_mais_a_cada_tentativa_e_reenvia_o_mesmo_evento(session):
    event = await _evento(session)
    ids = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids.append(request.headers["x-h2d-event-id"])
        return httpx.Response(503, text="fora do ar")

    async with _client(handler) as client:
        await deliver_pending(session, client, url=URL, secret=SEGREDO, now=AGORA)
        await session.refresh(event)
        assert event.status is OutboxStatus.PENDING and event.attempts == 1
        assert "503" in (event.last_error or "")
        primeira_espera = event.next_attempt_at - AGORA
        # Antes do prazo, nada é tentado de novo.
        assert await deliver_pending(session, client, url=URL, secret=SEGREDO, now=AGORA) == 0
        await deliver_pending(session, client, url=URL, secret=SEGREDO, now=event.next_attempt_at)
        await session.refresh(event)
        segunda_espera = event.next_attempt_at - (AGORA + primeira_espera)

    assert event.attempts == 2
    assert segunda_espera > primeira_espera
    assert len(set(ids)) == 1  # o mesmo event_id em todas as tentativas


async def test_n8n_fora_do_ar_nao_perde_o_aviso_e_entrega_ao_religar(session):
    event = await _evento(session)
    ligado = False

    def handler(request: httpx.Request) -> httpx.Response:
        if not ligado:
            raise httpx.ConnectError("sem rota para o host")
        return httpx.Response(200)

    async with _client(handler) as client:
        await deliver_pending(session, client, url=URL, secret=SEGREDO, now=AGORA)
        await session.refresh(event)
        assert event.status is OutboxStatus.PENDING and "ConnectError" in (event.last_error or "")
        ligado = True
        await deliver_pending(session, client, url=URL, secret=SEGREDO, now=event.next_attempt_at)

    await session.refresh(event)
    assert event.status is OutboxStatus.DELIVERED


async def test_desiste_depois_do_limite_de_tentativas(session):
    event = await _evento(session, attempts=MAX_ATTEMPTS - 1)

    async with _client(lambda request: httpx.Response(500)) as client:
        await deliver_pending(session, client, url=URL, secret=SEGREDO, now=AGORA)

    await session.refresh(event)
    assert event.status is OutboxStatus.FAILED and event.attempts == MAX_ATTEMPTS


# --- Rotas que o n8n chama (HMAC no sentido contrário) --------------------------------------------


@pytest.fixture
def com_segredo(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "n8n_hmac_secret", SecretStr(SEGREDO))


def _assinado(corpo: bytes = b"", segredo: str = SEGREDO, agora: datetime | None = None) -> dict:
    ts = str(int((agora or datetime.now(UTC)).timestamp()))
    return {"X-H2D-Timestamp": ts, "X-H2D-Signature": sign(segredo, ts, corpo)}


async def test_rota_do_n8n_aceita_assinatura_valida(client, com_segredo):
    response = await client.post("/api/hooks/n8n/ping", headers=_assinado())

    assert response.status_code == 200 and response.json() == {"ok": True}


@pytest.mark.parametrize(
    "cabecalhos",
    [
        {},
        {"X-H2D-Timestamp": "1", "X-H2D-Signature": "sha256=abc"},
        _assinado(segredo="segredo-errado"),
        _assinado(agora=datetime.now(UTC) - timedelta(hours=1)),
    ],
)
async def test_rota_do_n8n_recusa_sem_assinatura_valida(client, com_segredo, cabecalhos):
    response = await client.post("/api/hooks/n8n/ping", headers=cabecalhos)

    assert response.status_code == 401


async def test_rota_do_n8n_fica_desligada_sem_segredo(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "n8n_hmac_secret", None)

    response = await client.post("/api/hooks/n8n/ping", headers=_assinado())

    assert response.status_code == 503
