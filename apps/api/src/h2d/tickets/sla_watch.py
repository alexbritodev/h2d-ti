"""Vigia de SLA: gera um alerta quando o prazo de resolução passa de 75% e outro quando estoura.

Cada nível dispara **uma única vez** por chamado. O alerta vira uma linha na linha do tempo e um
evento no outbox, na mesma transação: a entrega ao n8n (com novas tentativas) cuida do e-mail, então
um e-mail que falha não perde o alerta nem o repete.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.models import Technician, Ticket, TicketEvent, TicketStatus, User
from h2d.tickets.rules import sla_state
from h2d.tickets.service import add_event, emit

LEVEL_AT_RISK = 75
LEVEL_BREACHED = 100


async def _already_alerted(
    session: AsyncSession, ticket_ids: list[uuid.UUID]
) -> dict[uuid.UUID, set[int]]:
    sent: dict[uuid.UUID, set[int]] = {}
    rows = await session.execute(
        select(TicketEvent.ticket_id, TicketEvent.payload).where(
            TicketEvent.type == "sla_alert", TicketEvent.ticket_id.in_(ticket_ids)
        )
    )
    for ticket_id, payload in rows:
        sent.setdefault(ticket_id, set()).add(int(payload.get("level", 0)))
    return sent


async def emit_sla_alerts(
    session: AsyncSession, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Cria os alertas que faltam. Devolve um resumo de cada um (para o corpo da resposta)."""
    now = now or datetime.now(UTC)
    tickets = list(
        await session.scalars(
            select(Ticket)
            .where(Ticket.status != TicketStatus.RESOLVED, Ticket.resolution_due.is_not(None))
            .order_by(Ticket.created_at)
            # Bloqueia as linhas: duas verificações ao mesmo tempo não duplicam o alerta.
            .with_for_update(skip_locked=True)
        )
    )
    if not tickets:
        return []
    sent = await _already_alerted(session, [t.id for t in tickets])

    alerts: list[dict[str, Any]] = []
    for ticket in tickets:
        state = sla_state(
            created_at=ticket.created_at, due=ticket.resolution_due, now=now, done_at=None
        )
        level = {"at_risk": LEVEL_AT_RISK, "breached": LEVEL_BREACHED}.get(state)
        if level is None or level in sent.get(ticket.id, set()):
            continue
        requester = await session.get_one(User, ticket.requester_id)
        assignee: User | None = None
        if ticket.technician_id:
            technician = await session.get_one(Technician, ticket.technician_id)
            assignee = await session.get_one(User, technician.user_id)
        reason = (
            "Prazo de resolução passou de 75%"
            if level == LEVEL_AT_RISK
            else "Prazo de resolução estourado"
        )
        add_event(session, ticket, "sla_alert", payload={"level": level}, reason=reason)
        payload = {
            "ticket_id": str(ticket.id),
            "code": ticket.code,
            "summary": ticket.summary,
            "priority": ticket.priority.value if ticket.priority else None,
            "level": level,
            "resolution_due": ticket.resolution_due.isoformat() if ticket.resolution_due else None,
            "requester": {"name": requester.name, "email": requester.email},
            "assignee": {"name": assignee.name, "email": assignee.email} if assignee else None,
            # Estouro avisa também o líder; 75% fica com quem está atendendo.
            "notify_leader": level == LEVEL_BREACHED,
        }
        emit(session, "ticket.sla_alert", payload)
        alerts.append({"code": ticket.code, "level": level})
    await session.flush()
    return alerts
