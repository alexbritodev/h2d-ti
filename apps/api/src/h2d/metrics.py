"""Números do dashboard. Cada um tem uma definição fixa (abaixo) e um teste que o confere com SQL
escrito à mão (tests/test_metrics.py).

Período: os últimos N dias de calendário em America/Sao_Paulo, contando hoje (N = 1 é só hoje).

- **Conversa** conta quando tem ao menos uma pergunta do usuário (abrir o chat e sair não conta).
- **Defleção** = conversas sem chamado e não escalonadas / conversas. O que o assistente resolveu,
  ou o que o usuário deixou de levar adiante, sem gerar trabalho para a TI.
- **Custo por conversa** = soma de `llm_calls.cost_usd` das conversas do período / conversas.
  Inclui a classificação do chamado, que também é uma chamada ligada à conversa.
- **Volume** = conversas e chamados criados por dia.
- **SLA cumprido** = chamados resolvidos no período, com prazo, resolvidos até o prazo / resolvidos
  com prazo. Chamado ainda aberto e vencido aparece à parte, em `open_overdue`.
"""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import DateTime, bindparam, exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.models import (
    Conversation,
    ConversationStatus,
    LlmCall,
    Message,
    MessageRole,
    Ticket,
    TicketStatus,
)

TIMEZONE = "America/Sao_Paulo"
MAX_DAYS = 90


class DayVolume(BaseModel):
    day: str  # AAAA-MM-DD, no fuso de São Paulo
    conversations: int
    tickets: int


class BotMetrics(BaseModel):
    conversations: int
    deflected: int
    with_ticket: int
    escalated_without_ticket: int
    # 0 a 1; None quando não há conversas no período.
    deflection_rate: float | None


class CostMetrics(BaseModel):
    llm_calls: int
    total_usd: Decimal
    per_conversation_usd: Decimal | None


class VolumeMetrics(BaseModel):
    conversations: int
    tickets: int
    by_day: list[DayVolume]


class SlaMetrics(BaseModel):
    resolved_with_due: int
    met: int
    breached: int
    # 0 a 1; None quando nada foi resolvido com prazo no período.
    met_rate: float | None
    # Abertos com o prazo de resolução já vencido (foto de agora, não do período).
    open_overdue: int


class Overview(BaseModel):
    days: int
    since: datetime
    bot: BotMetrics
    cost: CostMetrics
    volume: VolumeMetrics
    sla: SlaMetrics


_SINCE_SQL = text(
    """
    SELECT (date_trunc('day', timezone(:tz, :now)) - make_interval(days => :back))
           AT TIME ZONE :tz
    """
).bindparams(bindparam("now", type_=DateTime(timezone=True)))

# Uma linha por dia do período, com zeros nos dias sem movimento.
_VOLUME_SQL = text(
    """
    SELECT to_char(d.day, 'YYYY-MM-DD') AS day,
           (SELECT count(*) FROM conversations c
             WHERE timezone(:tz, c.created_at)::date = d.day AND c.created_at <= :now
               AND EXISTS (SELECT 1 FROM messages m
                            WHERE m.conversation_id = c.id AND m.role = 'user')) AS conversations,
           (SELECT count(*) FROM tickets t
             WHERE timezone(:tz, t.created_at)::date = d.day AND t.created_at <= :now) AS tickets
      FROM generate_series(timezone(:tz, :since)::date, timezone(:tz, :now)::date,
                           interval '1 day') AS d(day)
     ORDER BY d.day
    """
).bindparams(
    bindparam("now", type_=DateTime(timezone=True)),
    bindparam("since", type_=DateTime(timezone=True)),
)


def _rate(part: int, whole: int) -> float | None:
    return part / whole if whole else None


async def overview(session: AsyncSession, days: int, *, now: datetime | None = None) -> Overview:
    days = max(1, min(days, MAX_DAYS))
    now = now or datetime.now(UTC)
    since = await session.scalar(_SINCE_SQL, {"tz": TIMEZONE, "now": now, "back": days - 1})
    if since is None:  # o SELECT sempre devolve uma linha; isto só acalma o tipo
        raise RuntimeError("Não foi possível calcular o início do período")

    asked = exists().where(
        Message.conversation_id == Conversation.id, Message.role == MessageRole.USER
    )
    has_ticket = exists().where(Ticket.conversation_id == Conversation.id)
    in_period = (Conversation.created_at >= since, Conversation.created_at <= now, asked)

    conversations = await session.scalar(select(func.count()).where(*in_period)) or 0
    with_ticket = await session.scalar(select(func.count()).where(*in_period, has_ticket)) or 0
    escalated_without_ticket = (
        await session.scalar(
            select(func.count()).where(
                *in_period, ~has_ticket, Conversation.status == ConversationStatus.ESCALATED
            )
        )
        or 0
    )
    deflected = conversations - with_ticket - escalated_without_ticket

    conversation_ids = select(Conversation.id).where(*in_period)
    calls, total_cost = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(
                LlmCall.conversation_id.in_(conversation_ids)
            )
        )
    ).one()
    total_cost = Decimal(total_cost)

    rows = (await session.execute(_VOLUME_SQL, {"tz": TIMEZONE, "now": now, "since": since})).all()
    by_day = [DayVolume(day=r.day, conversations=r.conversations, tickets=r.tickets) for r in rows]

    resolved = (
        Ticket.resolved_at >= since,
        Ticket.resolved_at <= now,
        Ticket.resolution_due.is_not(None),
    )
    resolved_with_due = await session.scalar(select(func.count()).where(*resolved)) or 0
    met = (
        await session.scalar(
            select(func.count()).where(*resolved, Ticket.resolved_at <= Ticket.resolution_due)
        )
        or 0
    )
    open_overdue = (
        await session.scalar(
            select(func.count()).where(
                Ticket.status != TicketStatus.RESOLVED,
                Ticket.resolution_due.is_not(None),
                Ticket.resolution_due < now,
            )
        )
        or 0
    )

    return Overview(
        days=days,
        since=since,
        bot=BotMetrics(
            conversations=conversations,
            deflected=deflected,
            with_ticket=with_ticket,
            escalated_without_ticket=escalated_without_ticket,
            deflection_rate=_rate(deflected, conversations),
        ),
        cost=CostMetrics(
            llm_calls=calls,
            total_usd=total_cost,
            per_conversation_usd=total_cost / conversations if conversations else None,
        ),
        volume=VolumeMetrics(
            conversations=sum(d.conversations for d in by_day),
            tickets=sum(d.tickets for d in by_day),
            by_day=by_day,
        ),
        sla=SlaMetrics(
            resolved_with_due=resolved_with_due,
            met=met,
            breached=resolved_with_due - met,
            met_rate=_rate(met, resolved_with_due),
            open_overdue=open_overdue,
        ),
    )
