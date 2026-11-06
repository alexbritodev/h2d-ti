"""Cada número do dashboard é conferido de duas formas: contra o valor esperado dos dados montados
aqui (contas feitas à mão) e contra SQL escrito à mão, sem passar pelo código de `h2d.metrics`.

Agora = 06/11/2026 12:00 em São Paulo (15:00 UTC), período de 3 dias: começa em 04/11 00:00 em
São Paulo (03:00 UTC). São Paulo está em UTC-3, sem horário de verão.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.metrics import overview
from h2d.models import (
    Conversation,
    ConversationStatus,
    LlmCall,
    Message,
    MessageRole,
    Role,
    Ticket,
    TicketStatus,
)
from tests.conftest import PASSWORD

NOW = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


async def _conversation(
    session: AsyncSession,
    user_id: uuid.UUID,
    created_at: datetime,
    status: ConversationStatus,
    *,
    asked: bool = True,
) -> Conversation:
    conversation = Conversation(user_id=user_id, status=status, created_at=created_at)
    session.add(conversation)
    await session.flush()
    if asked:
        session.add(
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="pergunta",
                created_at=created_at,
            )
        )
    return conversation


async def _ticket(
    session: AsyncSession,
    requester_id: uuid.UUID,
    created_at: datetime,
    *,
    conversation: Conversation | None = None,
    due: datetime | None = None,
    resolved_at: datetime | None = None,
) -> Ticket:
    ticket = Ticket(
        requester_id=requester_id,
        conversation_id=conversation.id if conversation else None,
        summary="chamado de teste",
        status=TicketStatus.RESOLVED if resolved_at else TicketStatus.ASSIGNED,
        resolution_due=due,
        resolved_at=resolved_at,
        created_at=created_at,
    )
    session.add(ticket)
    await session.flush()
    return ticket


def _call(conversation: Conversation | None, cost: str, created_at: datetime) -> LlmCall:
    return LlmCall(
        purpose="answer",
        model="modelo",
        status="ok",
        cost_usd=Decimal(cost),
        conversation_id=conversation.id if conversation else None,
        created_at=created_at,
    )


@pytest.fixture
async def dataset(session: AsyncSession, make_user) -> None:
    user = await make_user(email="solicitante@h2d.local")

    c1 = await _conversation(session, user.id, at(4, 10), ConversationStatus.RESOLVED)
    c2 = await _conversation(session, user.id, at(5, 13), ConversationStatus.ESCALATED)
    c3 = await _conversation(session, user.id, at(5, 14), ConversationStatus.ESCALATED)
    c4 = await _conversation(session, user.id, at(6, 12), ConversationStatus.OPEN)
    # Fora da conta: sem pergunta do usuário.
    await _conversation(session, user.id, at(6, 13), ConversationStatus.OPEN, asked=False)
    # Fora do período por 1 hora: 04/11 02:00 UTC ainda é 03/11 23:00 em São Paulo.
    c6 = await _conversation(session, user.id, at(4, 2), ConversationStatus.RESOLVED)

    session.add_all(
        [
            _call(c1, "0.010000", at(4, 10)),
            _call(c1, "0.005000", at(4, 10, 1)),
            _call(c2, "0.020000", at(5, 13)),
            _call(c4, "0", at(6, 12)),
            _call(c6, "1.000000", at(4, 2)),  # conversa fora do período
            _call(None, "5.000000", at(5, 9)),  # sem conversa
        ]
    )

    # Chamados criados no período: T1 (05/11), T2 (04/11 00:00 em SP, limite exato), T3 (04/11
    # 22:00 em SP) e T4 (06/11). T5 nasceu antes.
    await _ticket(
        session, user.id, at(5, 13, 30), conversation=c2, due=at(6, 12), resolved_at=at(6, 10)
    )
    await _ticket(session, user.id, at(4, 3), due=at(6, 12), resolved_at=at(6, 14))
    await _ticket(session, user.id, at(5, 1), due=None, resolved_at=at(6, 9))
    await _ticket(session, user.id, at(6, 8), due=at(6, 11))
    await _ticket(session, user.id, at(3, 12), due=at(3, 13), resolved_at=at(3, 12, 30))
    # c3 escalou sem ter virado chamado.
    assert c3.status is ConversationStatus.ESCALATED
    await session.flush()


async def test_defleccao(session: AsyncSession, dataset) -> None:
    result = await overview(session, 3, now=NOW)

    # 4 conversas com pergunta no período: C1 e C4 resolvidas sem chamado; C2 virou chamado;
    # C3 escalou sem chamado.
    assert result.bot.conversations == 4
    assert result.bot.deflected == 2
    assert result.bot.with_ticket == 1
    assert result.bot.escalated_without_ticket == 1
    assert result.bot.deflection_rate == 0.5

    # SQL à mão, sem reaproveitar nada do módulo.
    row = (
        await session.execute(
            text(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM tickets t
                                                           WHERE t.conversation_id = c.id)
                                          AND c.status <> 'escalated') AS deflected
                  FROM conversations c
                 WHERE c.created_at >= '2026-11-04 03:00:00+00' AND c.created_at <= :now
                   AND EXISTS (SELECT 1 FROM messages m
                                WHERE m.conversation_id = c.id AND m.role = 'user')
                """
            ),
            {"now": NOW},
        )
    ).one()
    assert (row.total, row.deflected) == (4, 2)


async def test_custo_por_conversa(session: AsyncSession, dataset) -> None:
    result = await overview(session, 3, now=NOW)

    # Só as chamadas das 4 conversas do período: 0,010 + 0,005 + 0,020 + 0 = 0,035.
    assert result.cost.llm_calls == 4
    assert result.cost.total_usd == Decimal("0.035")
    assert result.cost.per_conversation_usd == Decimal("0.035") / 4

    total = await session.scalar(
        text(
            """
            SELECT coalesce(sum(l.cost_usd), 0)
              FROM llm_calls l
              JOIN conversations c ON c.id = l.conversation_id
             WHERE c.created_at >= '2026-11-04 03:00:00+00' AND c.created_at <= :now
               AND EXISTS (SELECT 1 FROM messages m
                            WHERE m.conversation_id = c.id AND m.role = 'user')
            """
        ),
        {"now": NOW},
    )
    assert total == Decimal("0.035000")


async def test_volume_por_dia_no_fuso_de_sao_paulo(session: AsyncSession, dataset) -> None:
    result = await overview(session, 3, now=NOW)

    assert [(d.day, d.conversations, d.tickets) for d in result.volume.by_day] == [
        ("2026-11-04", 1, 2),
        ("2026-11-05", 2, 1),
        ("2026-11-06", 1, 1),
    ]
    assert result.volume.conversations == 4
    assert result.volume.tickets == 4

    rows = (
        await session.execute(
            text(
                """
                SELECT to_char(timezone('America/Sao_Paulo', created_at), 'YYYY-MM-DD') AS day,
                       count(*) AS n
                  FROM tickets
                 WHERE created_at >= '2026-11-04 03:00:00+00' AND created_at <= :now
                 GROUP BY 1 ORDER BY 1
                """
            ),
            {"now": NOW},
        )
    ).all()
    assert [(r.day, r.n) for r in rows] == [("2026-11-04", 2), ("2026-11-05", 1), ("2026-11-06", 1)]


async def test_sla_cumprido(session: AsyncSession, dataset) -> None:
    result = await overview(session, 3, now=NOW)

    # Resolvidos no período e com prazo: T1 (no prazo) e T2 (depois do prazo). T3 não tem prazo e
    # T5 foi resolvido antes do período. T4 está aberto e vencido.
    assert result.sla.resolved_with_due == 2
    assert result.sla.met == 1
    assert result.sla.breached == 1
    assert result.sla.met_rate == 0.5
    assert result.sla.open_overdue == 1

    row = (
        await session.execute(
            text(
                """
                SELECT count(*) AS resolved,
                       count(*) FILTER (WHERE resolved_at <= resolution_due) AS met,
                       (SELECT count(*) FROM tickets
                         WHERE status <> 'resolved' AND resolution_due < :now) AS overdue
                  FROM tickets
                 WHERE resolved_at >= '2026-11-04 03:00:00+00' AND resolved_at <= :now
                   AND resolution_due IS NOT NULL
                """
            ),
            {"now": NOW},
        )
    ).one()
    assert (row.resolved, row.met, row.overdue) == (2, 1, 1)


async def test_sem_dados_nao_divide_por_zero(session: AsyncSession) -> None:
    result = await overview(session, 7, now=NOW)

    assert result.bot.conversations == 0
    assert result.bot.deflection_rate is None
    assert result.cost.per_conversation_usd is None
    assert result.sla.met_rate is None
    assert len(result.volume.by_day) == 7
    assert all(d.conversations == 0 and d.tickets == 0 for d in result.volume.by_day)


@pytest.mark.parametrize(
    ("role", "expected"), [(Role.USER, 403), (Role.TECH, 200), (Role.ADMIN, 200)]
)
async def test_quem_pode_ler_o_dashboard(client, make_user, role, expected) -> None:
    await make_user(email="alguem@h2d.local", role=role)
    await client.post("/api/auth/login", json={"email": "alguem@h2d.local", "password": PASSWORD})

    assert (await client.get("/api/metrics/overview")).status_code == expected


async def test_dashboard_exige_login_e_periodo_valido(client, make_user) -> None:
    assert (await client.get("/api/metrics/overview")).status_code == 401

    await make_user(email="chefe@h2d.local", role=Role.ADMIN)
    await client.post("/api/auth/login", json={"email": "chefe@h2d.local", "password": PASSWORD})
    assert (await client.get("/api/metrics/overview?days=0")).status_code == 422
    assert (await client.get("/api/metrics/overview?days=91")).status_code == 422


async def test_tecnico_so_le_o_dashboard(client, make_user) -> None:
    await make_user(email="tec@h2d.local", role=Role.TECH)
    await client.post("/api/auth/login", json={"email": "tec@h2d.local", "password": PASSWORD})

    # A única rota de métricas é GET: qualquer escrita é recusada.
    for method in ("post", "put", "patch", "delete"):
        response = await getattr(client, method)("/api/metrics/overview")
        assert response.status_code == 405
