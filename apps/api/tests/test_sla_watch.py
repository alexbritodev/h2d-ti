from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.models import (
    OutboxEvent,
    Priority,
    Role,
    Technician,
    Ticket,
    TicketEvent,
    TicketStatus,
)
from h2d.outbox import sign
from h2d.tickets.sla_watch import emit_sla_alerts

# O chamado nasce às 09h e tem 4 horas para resolver: 75% = 12h, 100% = 13h.
CRIADO = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
PRAZO = CRIADO + timedelta(hours=4)


async def _chamado(session: AsyncSession, make_user, **kw) -> Ticket:
    solicitante = await make_user(email=f"s{len(kw)}{id(kw)}@h2d.local")
    ticket = Ticket(
        requester_id=solicitante.id,
        summary="VPN não conecta",
        description="",
        priority=Priority.P2,
        status=kw.pop("status", TicketStatus.ASSIGNED),
        created_at=CRIADO,
        resolution_due=kw.pop("resolution_due", PRAZO),
        **kw,
    )
    session.add(ticket)
    await session.flush()
    await session.refresh(ticket)
    return ticket


async def _eventos(session: AsyncSession) -> list[OutboxEvent]:
    return list(
        await session.scalars(select(OutboxEvent).where(OutboxEvent.type == "ticket.sla_alert"))
    )


async def test_no_prazo_nao_alerta(session, make_user):
    await _chamado(session, make_user)

    alertas = await emit_sla_alerts(session, now=CRIADO + timedelta(hours=1))

    assert alertas == [] and await _eventos(session) == []


async def test_alerta_de_75_por_cento_dispara_uma_unica_vez(session, make_user):
    ticket = await _chamado(session, make_user)
    agora = CRIADO + timedelta(hours=3, minutes=10)

    primeira = await emit_sla_alerts(session, now=agora)
    segunda = await emit_sla_alerts(session, now=agora + timedelta(minutes=5))

    assert primeira == [{"code": ticket.code, "level": 75}]
    assert segunda == []
    eventos = await _eventos(session)
    assert len(eventos) == 1
    assert eventos[0].payload["level"] == 75 and eventos[0].payload["notify_leader"] is False
    linha = list(await session.scalars(select(TicketEvent).where(TicketEvent.type == "sla_alert")))
    assert [e.payload["level"] for e in linha] == [75]


async def test_estouro_alerta_uma_vez_e_avisa_o_lider_e_cada_nivel_so_uma_vez(session, make_user):
    ticket = await _chamado(session, make_user)

    await emit_sla_alerts(session, now=CRIADO + timedelta(hours=3, minutes=30))
    estouro = await emit_sla_alerts(session, now=PRAZO + timedelta(minutes=1))
    repetido = await emit_sla_alerts(session, now=PRAZO + timedelta(hours=2))

    assert estouro == [{"code": ticket.code, "level": 100}]
    assert repetido == []
    niveis = sorted(e.payload["level"] for e in await _eventos(session))
    assert niveis == [75, 100]
    estouro_evento = next(e for e in await _eventos(session) if e.payload["level"] == 100)
    assert estouro_evento.payload["notify_leader"] is True


async def test_se_o_vigia_ficou_parado_so_o_estouro_e_avisado(session, make_user):
    ticket = await _chamado(session, make_user)

    alertas = await emit_sla_alerts(session, now=PRAZO + timedelta(hours=1))

    assert alertas == [{"code": ticket.code, "level": 100}]


async def test_chamado_resolvido_ou_sem_prazo_nunca_alerta(session, make_user):
    await _chamado(session, make_user, status=TicketStatus.RESOLVED)
    sem_prazo = await _chamado(session, make_user, resolution_due=None)

    alertas = await emit_sla_alerts(session, now=PRAZO + timedelta(days=3))

    assert alertas == []
    assert sem_prazo.status is TicketStatus.ASSIGNED


async def test_alerta_leva_o_responsavel_para_o_e_mail(session, make_user):
    tecnico = await make_user(email="tec@h2d.local", role=Role.TECH)
    registro = Technician(user_id=tecnico.id)
    session.add(registro)
    await session.flush()
    await _chamado(session, make_user, technician_id=registro.id)

    await emit_sla_alerts(session, now=CRIADO + timedelta(hours=3, minutes=30))

    [evento] = await _eventos(session)
    assert evento.payload["assignee"]["email"] == "tec@h2d.local"


# --- Rota assinada --------------------------------------------------------------------------------

SEGREDO = "segredo-de-teste-do-vigia"


@pytest.fixture
def com_segredo(monkeypatch):
    monkeypatch.setattr(get_settings(), "n8n_hmac_secret", SecretStr(SEGREDO))


def _assinado(segredo: str = SEGREDO) -> dict:
    ts = str(int(datetime.now(UTC).timestamp()))
    return {"X-H2D-Timestamp": ts, "X-H2D-Signature": sign(segredo, ts, b"")}


async def test_rota_sem_assinatura_valida_recebe_401_e_nada_e_criado(
    client, session, make_user, com_segredo
):
    await _chamado(session, make_user, resolution_due=datetime.now(UTC) - timedelta(hours=1))

    sem = await client.post("/api/hooks/n8n/sla-check")
    errada = await client.post("/api/hooks/n8n/sla-check", headers=_assinado("outro-segredo"))

    assert sem.status_code == 401 and errada.status_code == 401
    assert await _eventos(session) == []


async def test_rota_assinada_gera_o_alerta_uma_vez(client, session, make_user, com_segredo):
    ticket = await _chamado(
        session, make_user, resolution_due=datetime.now(UTC) - timedelta(hours=1)
    )

    primeira = await client.post("/api/hooks/n8n/sla-check", headers=_assinado())
    segunda = await client.post("/api/hooks/n8n/sla-check", headers=_assinado())

    assert primeira.status_code == 200
    assert primeira.json() == {"alerts": [{"code": ticket.code, "level": 100}]}
    assert segunda.json() == {"alerts": []}
