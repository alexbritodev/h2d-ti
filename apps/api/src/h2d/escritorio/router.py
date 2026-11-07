"""Rotas do escritório virtual: configuração, atendimentos, replay, tempo real (SSE) e webhook.

Com ESCRITORIO_VIRTUAL_ENABLED desligada, tudo responde 404 (só a configuração responde, dizendo
que está desligado, para o menu saber que não deve aparecer).

Quem vê o quê: usuário comum só os eventos dos próprios atendimentos; TI (técnico e admin), todos.
O SSE consulta o banco a cada segundo em vez de depender de memória do processo: assim funciona
com mais de um processo da API e o worker, e a reconexão retoma pelo `Last-Event-ID`.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.db import get_sessionmaker
from h2d.deps import CurrentUser, SessionDep
from h2d.escritorio.events import build_event, is_enabled
from h2d.escritorio.models import AgentEvent
from h2d.models import Role, User
from h2d.routers.hooks import verified_n8n

POLL_SECONDS = 1.0
HEARTBEAT_SECONDS = 15.0
# O navegador reconecta sozinho (EventSource) e retoma pelo Last-Event-ID.
STREAM_MAX_SECONDS = 300.0
# Eventos são gravados em segundo plano e podem chegar um pouco atrasados.
OVERLAP = timedelta(seconds=5)
BATCH = 200
ACTIVE_WINDOW = timedelta(seconds=90)

Room = Literal["recepcao", "triagem", "rag", "banco", "tecnicos", "auditoria"]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def require_enabled() -> None:
    if not is_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Não encontrado")


router = APIRouter(prefix="/escritorio", tags=["escritorio"])
hooks_router = APIRouter(
    prefix="/hooks/n8n/escritorio", tags=["hooks"], dependencies=[Depends(verified_n8n)]
)


class EscritorioConfigOut(BaseModel):
    enabled: bool
    demo: bool


class AgentEventOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    room: str
    agent_name: str
    action: str
    summary: str
    metadata: dict[str, Any]
    created_at: datetime


class AtendimentoOut(BaseModel):
    """Um atendimento: a conversa e, se houver, o chamado que nasceu dela."""

    key: str
    conversation_id: uuid.UUID | None
    ticket_id: uuid.UUID | None
    ticket_code: str | None
    events: int
    started_at: datetime
    last_at: datetime
    last_room: str
    last_summary: str
    active: bool


class AgentEventIn(BaseModel):
    room: Room
    action: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=500)
    agent_name: str | None = Field(default=None, max_length=60)
    ticket_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _out(event: AgentEvent) -> AgentEventOut:
    return AgentEventOut(
        id=event.id,
        ticket_id=event.ticket_id,
        conversation_id=event.conversation_id,
        room=event.room,
        agent_name=event.agent_name,
        action=event.action,
        summary=event.summary,
        metadata=event.event_metadata or {},
        created_at=event.created_at,
    )


def _is_staff(user: User) -> bool:
    return user.role in (Role.TECH, Role.ADMIN)


def _conditions(
    user: User, ticket_id: uuid.UUID | None, conversation_id: uuid.UUID | None
) -> list[ColumnElement[bool]]:
    """Visibilidade (dono ou TI) e recorte por atendimento. O chamado inclui a conversa dele."""
    conds: list[ColumnElement[bool]] = []
    if not _is_staff(user):
        conds.append(AgentEvent.user_id == user.id)
    if conversation_id is not None:
        conds.append(AgentEvent.conversation_id == conversation_id)
    if ticket_id is not None:
        conversations = select(AgentEvent.conversation_id).where(
            AgentEvent.ticket_id == ticket_id, AgentEvent.conversation_id.is_not(None)
        )
        conds.append(
            or_(AgentEvent.ticket_id == ticket_id, AgentEvent.conversation_id.in_(conversations))
        )
    return conds


@router.get("/config", operation_id="getEscritorioConfig")
async def get_config(_: CurrentUser) -> EscritorioConfigOut:
    settings = get_settings()
    enabled = settings.escritorio_virtual_enabled
    return EscritorioConfigOut(enabled=enabled, demo=enabled and settings.escritorio_virtual_demo)


@router.get(
    "/atendimentos",
    operation_id="listEscritorioAtendimentos",
    dependencies=[Depends(require_enabled)],
)
async def list_atendimentos(
    session: SessionDep,
    user: CurrentUser,
    hours: Annotated[int, Query(ge=1, le=720)] = 72,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[AtendimentoOut]:
    """Atendimentos com eventos recentes, o mais novo primeiro (seletor da tela)."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = (
        await session.scalars(
            select(AgentEvent)
            .where(AgentEvent.created_at >= since, *_conditions(user, None, None))
            .order_by(AgentEvent.created_at.desc(), AgentEvent.id.desc())
            .limit(1000)
        )
    ).all()
    groups: dict[uuid.UUID, list[AgentEvent]] = {}
    for event in rows:
        key = event.conversation_id or event.ticket_id
        if key is not None:
            groups.setdefault(key, []).append(event)  # do mais novo para o mais antigo
    now = datetime.now(UTC)
    result: list[AtendimentoOut] = []
    for key, events in groups.items():
        latest, oldest = events[0], events[-1]
        code = next(
            (str(e.event_metadata["codigo"]) for e in events if e.event_metadata.get("codigo")),
            None,
        )
        result.append(
            AtendimentoOut(
                key=str(key),
                conversation_id=latest.conversation_id,
                ticket_id=next((e.ticket_id for e in events if e.ticket_id), None),
                ticket_code=code,
                events=len(events),
                started_at=oldest.created_at,
                last_at=latest.created_at,
                last_room=latest.room,
                last_summary=latest.summary,
                active=now - latest.created_at <= ACTIVE_WINDOW,
            )
        )
    return sorted(result, key=lambda a: a.last_at, reverse=True)[:limit]


@router.get(
    "/eventos", operation_id="listEscritorioEventos", dependencies=[Depends(require_enabled)]
)
async def list_events(
    session: SessionDep,
    user: CurrentUser,
    ticket_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    after: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> list[AgentEventOut]:
    """Eventos de um atendimento em ordem cronológica (modo replay)."""
    query = select(AgentEvent).where(*_conditions(user, ticket_id, conversation_id))
    if after is not None:
        query = query.where(AgentEvent.created_at > after)
    rows = await session.scalars(query.order_by(AgentEvent.created_at, AgentEvent.id).limit(limit))
    return [_out(e) for e in rows]


def get_session_factory() -> SessionFactory:
    """Cada consulta do stream abre e fecha a própria sessão. Os testes trocam esta função."""
    return get_sessionmaker()


def _sse(event: AgentEvent) -> str:
    return f"id: {event.id}\nevent: agent_event\ndata: {_out(event).model_dump_json()}\n\n"


async def _stream(
    request: Request,
    factory: SessionFactory,
    conds: list[ColumnElement[bool]],
    start_ts: datetime,
    start_id: uuid.UUID | None,
) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    started = last_beat = loop.time()
    cursor = start_ts
    seen: set[uuid.UUID] = set()
    yield ": conectado\n\n"
    while loop.time() - started < STREAM_MAX_SECONDS:
        if await request.is_disconnected():
            return
        async with factory() as session:
            rows = (
                await session.scalars(
                    select(AgentEvent)
                    .where(AgentEvent.created_at >= cursor - OVERLAP, *conds)
                    .order_by(AgentEvent.created_at, AgentEvent.id)
                    .limit(BATCH)
                )
            ).all()
        for event in rows:
            before_start = event.created_at < start_ts or (
                event.created_at == start_ts and (start_id is None or event.id <= start_id)
            )
            if before_start or event.id in seen:
                continue
            seen.add(event.id)
            cursor = max(cursor, event.created_at)
            last_beat = loop.time()
            yield _sse(event)
        if len(seen) > 5000:
            seen.clear()
        if loop.time() - last_beat >= HEARTBEAT_SECONDS:
            last_beat = loop.time()
            yield ": batimento\n\n"
        await asyncio.sleep(POLL_SECONDS)


@router.get(
    "/stream", operation_id="streamEscritorioEventos", dependencies=[Depends(require_enabled)]
)
async def stream_events(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    factory: Annotated[SessionFactory, Depends(get_session_factory)],
    ticket_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    after: datetime | None = None,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Eventos novos em SSE. Sem `after`, só o que acontecer daqui para frente (ao vivo)."""
    conds = _conditions(user, ticket_id, conversation_id)
    start_ts, start_id = after or datetime.now(UTC), None
    if last_event_id:
        try:
            last = await session.scalar(
                select(AgentEvent).where(AgentEvent.id == uuid.UUID(last_event_id), *conds)
            )
        except ValueError:
            last = None
        if last is not None:
            start_ts, start_id = last.created_at, last.id
    return StreamingResponse(
        _stream(request, factory, conds, start_ts, start_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@hooks_router.post(
    "/events", status_code=status.HTTP_201_CREATED, operation_id="n8nEscritorioEvent"
)
async def receive_event(body: AgentEventIn, session: SessionDep) -> AgentEventOut:
    """O n8n registra um passo dos agentes, com a mesma limpeza dos eventos da API."""
    require_enabled()
    event = build_event(
        room=body.room,
        action=body.action,
        summary=body.summary,
        agent_name=body.agent_name,
        ticket_id=body.ticket_id,
        conversation_id=body.conversation_id,
        user_id=body.user_id,
        metadata=body.metadata,
    )
    session.add(event)
    await session.commit()
    return _out(event)
