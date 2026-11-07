"""Chamados: o usuário vê os próprios; técnico e admin veem a fila inteira."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.deps import CurrentUser, SessionDep, require_role
from h2d.models import (
    Priority,
    Role,
    Skill,
    Technician,
    TechnicianSkill,
    Ticket,
    TicketEvent,
    TicketStatus,
    User,
)
from h2d.tickets.rules import sla_state
from h2d.tickets.service import add_event, emit

router = APIRouter(prefix="/tickets", tags=["tickets"])

StaffActor = Annotated[User, Depends(require_role(Role.TECH, Role.ADMIN))]
AdminActor = Annotated[User, Depends(require_role(Role.ADMIN))]


class TechnicianOut(BaseModel):
    id: uuid.UUID
    name: str
    is_available: bool
    open_tickets: int
    max_capacity: int
    skills: list[str]


class SlaOut(BaseModel):
    state: str
    first_response_due: datetime | None
    resolution_due: datetime | None


class TicketOut(BaseModel):
    id: uuid.UUID
    code: str
    summary: str
    status: TicketStatus
    priority: Priority | None
    category_id: uuid.UUID | None
    requester_id: uuid.UUID
    requester_name: str
    technician_id: uuid.UUID | None
    technician_name: str | None
    is_vip: bool
    confidence: float | None
    created_at: datetime
    updated_at: datetime
    sla: SlaOut


class EventOut(BaseModel):
    id: uuid.UUID
    type: str
    actor_name: str | None
    payload: dict[str, Any]
    reason: str | None
    created_at: datetime


class TicketDetail(TicketOut):
    description: str
    already_tried: str | None
    solution: str | None
    conversation_id: uuid.UUID | None
    events: list[EventOut]


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    technician_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=500)


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ResolveIn(BaseModel):
    solution: str = Field(min_length=3, max_length=4000)


# Quem pode mexer no andamento: o técnico dono do chamado e o admin.
_ALLOWED_STATUS = {
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.WAITING_USER,
    TicketStatus.TRIAGE,
}


async def _technician_of(session: AsyncSession, user: User) -> Technician | None:
    return await session.scalar(select(Technician).where(Technician.user_id == user.id))


async def _out(session: AsyncSession, ticket: Ticket) -> TicketOut:
    requester = await session.get_one(User, ticket.requester_id)
    technician = (
        await session.get(Technician, ticket.technician_id) if ticket.technician_id else None
    )
    technician_user = await session.get(User, technician.user_id) if technician else None
    now = datetime.now(UTC)
    state = sla_state(
        created_at=ticket.created_at,
        due=ticket.resolution_due,
        now=now,
        done_at=ticket.resolved_at,
    )
    return TicketOut(
        id=ticket.id,
        code=ticket.code,
        summary=ticket.summary,
        status=ticket.status,
        priority=ticket.priority,
        category_id=ticket.category_id,
        requester_id=ticket.requester_id,
        requester_name=requester.name,
        technician_id=ticket.technician_id,
        technician_name=technician_user.name if technician_user else None,
        is_vip=ticket.is_vip,
        confidence=float(ticket.confidence) if ticket.confidence is not None else None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        sla=SlaOut(
            state=state,
            first_response_due=ticket.first_response_due,
            resolution_due=ticket.resolution_due,
        ),
    )


async def _visible_ticket(session: AsyncSession, user: User, ticket_id: uuid.UUID) -> Ticket:
    ticket = await session.get(Ticket, ticket_id)
    # 404 também para chamado de outra pessoa: não revela que ele existe.
    if ticket is None or (user.role is Role.USER and ticket.requester_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chamado não encontrado")
    return ticket


@router.get("", operation_id="listTickets")
async def list_tickets(
    session: SessionDep,
    user: CurrentUser,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: Priority | None = None,
    mine: bool = False,
    triage: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TicketOut]:
    query = select(Ticket)
    if user.role is Role.USER:
        query = query.where(Ticket.requester_id == user.id)
    elif mine:
        technician = await _technician_of(session, user)
        query = query.where(
            Ticket.technician_id == (technician.id if technician else uuid.UUID(int=0))
        )
    if triage:
        query = query.where(Ticket.status == TicketStatus.TRIAGE)
    if status_filter is not None:
        query = query.where(Ticket.status == status_filter)
    if priority is not None:
        query = query.where(Ticket.priority == priority)
    # Mais urgente primeiro (P1...P4, sem prioridade por último), depois o mais antigo.
    rank = case(
        (Ticket.priority == Priority.P1, 1),
        (Ticket.priority == Priority.P2, 2),
        (Ticket.priority == Priority.P3, 3),
        (Ticket.priority == Priority.P4, 4),
        else_=5,
    )
    tickets = await session.scalars(
        query.order_by(rank, Ticket.created_at).limit(limit).offset(offset)
    )
    return [await _out(session, t) for t in tickets]


@router.get("/technicians", operation_id="listTechnicians")
async def list_technicians(session: SessionDep, _: StaffActor) -> list[TechnicianOut]:
    """Técnicos com carga atual e habilidades: base da reatribuição feita pelo admin."""
    rows = (
        await session.execute(
            select(Technician, User.name)
            .join(User, User.id == Technician.user_id)
            .order_by(User.name)
        )
    ).all()
    open_count = dict(
        (
            await session.execute(
                select(Ticket.technician_id, func.count())
                .where(Ticket.technician_id.is_not(None), Ticket.status != TicketStatus.RESOLVED)
                .group_by(Ticket.technician_id)
            )
        ).all()
    )
    skills: dict[uuid.UUID, list[str]] = {}
    for technician_id, name in await session.execute(
        select(TechnicianSkill.technician_id, Skill.name).join(
            Skill, Skill.id == TechnicianSkill.skill_id
        )
    ):
        skills.setdefault(technician_id, []).append(name)
    return [
        TechnicianOut(
            id=t.id,
            name=name,
            is_available=t.is_available,
            open_tickets=open_count.get(t.id, 0),
            max_capacity=t.max_capacity,
            skills=sorted(skills.get(t.id, [])),
        )
        for t, name in rows
    ]


@router.get("/{ticket_id}", operation_id="getTicket")
async def get_ticket(ticket_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> TicketDetail:
    ticket = await _visible_ticket(session, user, ticket_id)
    events = (
        await session.execute(
            select(TicketEvent, User.name)
            .outerjoin(User, User.id == TicketEvent.actor_id)
            .where(TicketEvent.ticket_id == ticket.id)
            .order_by(TicketEvent.created_at, TicketEvent.id)
        )
    ).all()
    out = await _out(session, ticket)
    return TicketDetail(
        **out.model_dump(),
        description=ticket.description,
        already_tried=ticket.already_tried,
        solution=ticket.solution,
        conversation_id=ticket.conversation_id,
        events=[
            EventOut(
                id=e.id,
                type=e.type,
                actor_name=name,
                payload=e.payload,
                reason=e.reason,
                created_at=e.created_at,
            )
            for e, name in events
        ],
    )


@router.patch("/{ticket_id}", operation_id="updateTicket")
async def update_ticket(
    ticket_id: uuid.UUID, body: TicketUpdate, session: SessionDep, actor: StaffActor
) -> TicketOut:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chamado não encontrado")
    if ticket.status is TicketStatus.RESOLVED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Chamado já resolvido")
    technician = await _technician_of(session, actor)
    is_owner = technician is not None and ticket.technician_id == technician.id
    if actor.role is Role.TECH and not is_owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só o técnico responsável mexe neste chamado"
        )

    now = datetime.now(UTC)
    if body.technician_id is not None:
        # Reatribuir é do admin (tech lead): é ele quem trata a fila de triagem.
        if actor.role is not Role.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o administrador reatribui chamados")
        target = await session.get(Technician, body.technician_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Técnico não encontrado")
        ticket.technician_id = target.id
        if ticket.status in (TicketStatus.NEW, TicketStatus.TRIAGE):
            ticket.status = TicketStatus.ASSIGNED
        target_user = await session.get_one(User, target.user_id)
        add_event(
            session,
            ticket,
            "assigned",
            actor=actor,
            payload={"technician_id": str(target.id)},
            reason=body.reason or "Atribuição manual",
        )
        requester = await session.get_one(User, ticket.requester_id)
        emit(
            session,
            "ticket.assigned",
            {
                "ticket_id": str(ticket.id),
                "code": ticket.code,
                "summary": ticket.summary,
                "priority": ticket.priority.value if ticket.priority else None,
                "requester": {"name": requester.name, "email": requester.email},
                "assignee": {"name": target_user.name, "email": target_user.email},
            },
        )

    if body.status is not None and body.status is not ticket.status:
        if body.status not in _ALLOWED_STATUS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Para encerrar, use a resolução com solução"
            )
        before = ticket.status
        ticket.status = body.status
        if body.status is TicketStatus.IN_PROGRESS and ticket.first_response_at is None:
            ticket.first_response_at = now
        add_event(
            session,
            ticket,
            "status_changed",
            actor=actor,
            payload={"from": before.value, "to": body.status.value},
            reason=body.reason,
        )
    await session.commit()
    await session.refresh(ticket)
    return await _out(session, ticket)


@router.post(
    "/{ticket_id}/comments", status_code=status.HTTP_201_CREATED, operation_id="commentTicket"
)
async def comment(
    ticket_id: uuid.UUID, body: CommentIn, session: SessionDep, user: CurrentUser
) -> EventOut:
    ticket = await _visible_ticket(session, user, ticket_id)
    event = add_event(session, ticket, "comment", actor=user, payload={"text": body.text})
    # A primeira resposta de alguém da TI encerra o prazo de primeira resposta.
    if user.role in (Role.TECH, Role.ADMIN) and ticket.first_response_at is None:
        ticket.first_response_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(event)
    return EventOut(
        id=event.id,
        type=event.type,
        actor_name=user.name,
        payload=event.payload,
        reason=None,
        created_at=event.created_at,
    )


@router.post("/{ticket_id}/resolve", operation_id="resolveTicket")
async def resolve_ticket(
    ticket_id: uuid.UUID, body: ResolveIn, session: SessionDep, actor: StaffActor
) -> TicketOut:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chamado não encontrado")
    if ticket.status is TicketStatus.RESOLVED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Chamado já resolvido")
    technician = await _technician_of(session, actor)
    if actor.role is Role.TECH and (technician is None or ticket.technician_id != technician.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só o técnico responsável resolve este chamado"
        )
    now = datetime.now(UTC)
    ticket.status = TicketStatus.RESOLVED
    ticket.solution = body.solution
    ticket.resolved_at = now
    if ticket.first_response_at is None:
        ticket.first_response_at = now
    add_event(session, ticket, "resolved", actor=actor, payload={"solution": body.solution})
    requester = await session.get_one(User, ticket.requester_id)
    emit(
        session,
        "ticket.resolved",
        {
            "ticket_id": str(ticket.id),
            "code": ticket.code,
            "summary": ticket.summary,
            "requester": {"name": requester.name, "email": requester.email},
        },
    )
    await session.commit()
    await session.refresh(ticket)
    return await _out(session, ticket)
