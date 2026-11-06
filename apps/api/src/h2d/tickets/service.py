"""Criação e andamento de chamados: classificar, calcular prioridade e prazo, rotear e registrar."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.chat.service import call_llm, llm_calls_today
from h2d.config import get_settings
from h2d.llm.client import LLM, LLMError
from h2d.models import (
    AppSetting,
    Category,
    Conversation,
    ConversationStatus,
    Message,
    OutboxEvent,
    Priority,
    Skill,
    SlaPolicy,
    SlaTarget,
    Technician,
    TechnicianSkill,
    Ticket,
    TicketEvent,
    TicketStatus,
    User,
)
from h2d.tickets import classify as clf
from h2d.tickets.rules import PRIORITY_WEIGHT, Candidate, priority_from, route, sla_due

DEFAULT_CONFIDENCE_THRESHOLD = 0.6
TIMEZONE = "America/Sao_Paulo"


async def get_setting(session: AsyncSession, key: str, default: Any) -> Any:
    row = await session.get(AppSetting, key)
    return row.value if row is not None else default


def add_event(
    session: AsyncSession,
    ticket: Ticket,
    type_: str,
    *,
    actor: User | None = None,
    payload: dict[str, Any] | None = None,
    reason: str | None = None,
) -> TicketEvent:
    event = TicketEvent(
        ticket_id=ticket.id,
        type=type_,
        actor_id=actor.id if actor else None,
        payload=payload or {},
        reason=reason,
        # Horário exato: a linha do tempo precisa manter a ordem dos fatos dentro da transação.
        created_at=datetime.now(UTC),
    )
    session.add(event)
    return event


def emit(session: AsyncSession, type_: str, payload: dict[str, Any]) -> OutboxEvent:
    """Evento para o n8n, na mesma transação do dado que o originou (padrão outbox)."""
    event = OutboxEvent(type=type_, payload=payload)
    session.add(event)
    return event


def _ticket_payload(
    ticket: Ticket, requester: User, technician_user: User | None
) -> dict[str, Any]:
    return {
        "ticket_id": str(ticket.id),
        "code": ticket.code,
        "summary": ticket.summary,
        "priority": ticket.priority.value if ticket.priority else None,
        "status": ticket.status.value,
        "requester": {"name": requester.name, "email": requester.email},
        "assignee": (
            {"name": technician_user.name, "email": technician_user.email}
            if technician_user
            else None
        ),
        "resolution_due": ticket.resolution_due.isoformat() if ticket.resolution_due else None,
    }


async def _candidates(session: AsyncSession) -> tuple[list[Candidate], dict[uuid.UUID, User]]:
    technicians = list(
        (
            await session.execute(
                select(Technician, User)
                .join(User, User.id == Technician.user_id)
                .where(User.is_active)
            )
        ).all()
    )
    skills: dict[uuid.UUID, set[uuid.UUID]] = {}
    for link in await session.scalars(select(TechnicianSkill)):
        skills.setdefault(link.technician_id, set()).add(link.skill_id)
    open_tickets = await session.execute(
        select(Ticket.technician_id, Ticket.priority, Ticket.created_at).where(
            Ticket.technician_id.is_not(None), Ticket.status != TicketStatus.RESOLVED
        )
    )
    count: dict[uuid.UUID, int] = {}
    weight: dict[uuid.UUID, int] = {}
    for technician_id, priority, _ in open_tickets:
        if technician_id is None:
            continue
        count[technician_id] = count.get(technician_id, 0) + 1
        weight[technician_id] = weight.get(technician_id, 0) + PRIORITY_WEIGHT.get(
            priority or Priority.P4, 1
        )
    last: dict[uuid.UUID, datetime] = {
        technician_id: when
        for technician_id, when in (
            await session.execute(
                select(Ticket.technician_id, func.max(Ticket.created_at))
                .where(Ticket.technician_id.is_not(None))
                .group_by(Ticket.technician_id)
            )
        )
        if technician_id is not None
    }
    users = {t.id: u for t, u in technicians}
    candidates = [
        Candidate(
            technician_id=t.id,
            skill_ids=frozenset(skills.get(t.id, set())),
            is_available=t.is_available,
            max_capacity=t.max_capacity,
            open_count=count.get(t.id, 0),
            open_weight=weight.get(t.id, 0),
            schedule=t.schedule or {},
            last_assigned_at=last.get(t.id),
        )
        for t, _ in technicians
    ]
    return candidates, users


async def _sla_minutes(
    session: AsyncSession, policy_id: uuid.UUID | None, priority: Priority
) -> tuple[int, int] | None:
    if policy_id is None:
        policy_id = await session.scalar(
            select(SlaPolicy.id)
            .order_by((SlaPolicy.name == "Padrão").desc(), SlaPolicy.name)
            .limit(1)
        )
    if policy_id is None:
        return None
    target = await session.get(SlaTarget, (policy_id, priority))
    return (target.first_response_minutes, target.resolution_minutes) if target else None


async def create_ticket(
    session: AsyncSession,
    *,
    requester: User,
    summary: str,
    description: str,
    conversation: Conversation | None = None,
    classification: clf.Classification | None = None,
    categories: list[clf.CategoryOption] | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Ticket:
    """Cria o chamado já classificado e roteado, ou na triagem manual quando falta confiança."""
    now = now or datetime.now(UTC)
    category = subcategory = None
    confidence = classification.confianca if classification else None
    classification_note = note
    if classification is not None:
        category, subcategory = clf.match_category(classification, categories or [])
        if category is None:
            # O modelo não pode inventar categoria: valor fora da lista vira triagem manual.
            confidence = 0.0
            classification_note = f"Categoria '{classification.categoria}' fora da lista cadastrada"

    priority = (
        priority_from(classification.impacto, classification.urgencia) if classification else None
    )
    ticket = Ticket(
        requester_id=requester.id,
        conversation_id=conversation.id if conversation else None,
        category_id=(subcategory or category).id if (subcategory or category) else None,  # type: ignore[arg-type]
        impact=classification.impacto if classification else None,
        urgency=classification.urgencia if classification else None,
        priority=priority,
        summary=summary[:300],
        description=description,
        already_tried=classification.ja_tentado if classification else None,
        confidence=confidence,
        classification=classification.model_dump(mode="json") if classification else None,
        is_vip=False,
        status=TicketStatus.NEW,
    )
    if priority is not None:
        policy_id = (category.sla_policy_id if category else None) or None
        minutes = await _sla_minutes(session, policy_id, priority)  # type: ignore[arg-type]
        if minutes:
            ticket.first_response_due = sla_due(now, minutes[0])
            ticket.resolution_due = sla_due(now, minutes[1])
    session.add(ticket)
    await session.flush()
    await session.refresh(ticket)

    add_event(
        session,
        ticket,
        "created",
        actor=requester,
        payload={"from_conversation": bool(conversation)},
    )
    if classification is not None:
        add_event(
            session,
            ticket,
            "classified",
            payload=ticket.classification or {},
            reason=classification_note,
        )

    candidates, users = await _candidates(session)
    required_skill = category.default_skill_id if category else None
    decision = route(
        candidates,
        required_skill_id=required_skill,  # type: ignore[arg-type]
        priority=priority,
        confidence=confidence,
        threshold=float(
            await get_setting(
                session, "classification_confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD
            )
        ),
        now=now,
        timezone=TIMEZONE,
    )
    technician_user = None
    if decision.technician_id is not None:
        ticket.technician_id = decision.technician_id
        ticket.status = TicketStatus.ASSIGNED
        technician_user = users[decision.technician_id]
        add_event(
            session,
            ticket,
            "assigned",
            payload={"technician_id": str(decision.technician_id)},
            reason=decision.reason,
        )
    else:
        ticket.status = TicketStatus.TRIAGE
        add_event(session, ticket, "triage", reason=decision.reason)
    await session.flush()

    payload = _ticket_payload(ticket, requester, technician_user)
    payload["notify_leader"] = decision.notify_leader
    emit(session, "ticket.created", payload)
    return ticket


def _transcript(messages: list[Message]) -> str:
    names = {"user": "Usuário", "assistant": "Assistente"}
    return "\n".join(f"{names[m.role.value]}: {m.content}" for m in messages)


async def create_ticket_from_conversation(
    session: AsyncSession,
    *,
    conversation: Conversation,
    requester: User,
    llm: LLM,
    reason: str,
    now: datetime | None = None,
) -> Ticket:
    """Escalona a conversa: classifica (se o modelo estiver disponível) e abre o chamado."""
    existing = await session.scalar(select(Ticket).where(Ticket.conversation_id == conversation.id))
    if existing is not None:
        return existing

    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    )
    transcript = _transcript(messages)
    first_user = next(
        (m.content for m in messages if m.role.value == "user"), "Pedido de atendimento"
    )

    categories = [
        clf.CategoryOption(c.id, c.name, c.parent_id, c.default_skill_id, c.sla_policy_id)
        for c in await session.scalars(select(Category).where(Category.is_active))
    ]
    skill_names = list(await session.scalars(select(Skill.name).order_by(Skill.name)))

    classification: clf.Classification | None = None
    note = f"Escalonado: {reason}"
    budget_left = await llm_calls_today(session) + 1 <= get_settings().llm_daily_request_limit
    if budget_left and categories:
        try:
            result = await call_llm(
                session,
                llm,
                "classify",
                clf.build_messages(
                    transcript=transcript,
                    categories=categories,
                    skills=skill_names,
                    department=requester.department,
                    vip=requester.is_vip,
                ),
                user=requester,
                conversation=conversation,
                temperature=0.0,
                max_tokens=600,
            )
            classification = clf.parse_classification(result.text)
        except LLMError as error:
            note = f"Escalonado: {reason}. Classificação indisponível ({str(error)[:120]})"
        except ValueError as error:
            note = f"Escalonado: {reason}. {error}"
    elif not budget_left:
        note = f"Escalonado: {reason}. Limite diário do modelo atingido"

    summary = (classification.resumo.splitlines()[0] if classification else first_user)[:300]
    ticket = await create_ticket(
        session,
        requester=requester,
        conversation=conversation,
        summary=summary,
        description=transcript,
        classification=classification,
        categories=categories,
        note=note,
        now=now,
    )
    ticket.is_vip = requester.is_vip
    add_event(session, ticket, "escalated", actor=requester, reason=note)
    conversation.status = ConversationStatus.ESCALATED
    await session.flush()
    return ticket
