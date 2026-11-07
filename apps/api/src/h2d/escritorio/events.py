"""Registro dos eventos dos agentes.

`emit_agent_event` é chamada nos pontos reais do atendimento. Ela nunca lança erro, não espera o
banco (a gravação roda em segundo plano, com sessão própria) e não faz nada com a flag desligada.
"""

import asyncio
import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from h2d.chat.masking import mask_sensitive
from h2d.config import get_settings
from h2d.db import get_sessionmaker
from h2d.escritorio.models import AgentEvent

log = logging.getLogger("h2d.escritorio")

ROOMS = ("recepcao", "triagem", "rag", "banco", "tecnicos", "auditoria")
AGENT_BY_ROOM = {
    "recepcao": "Chatbot",
    "triagem": "Classificador",
    "rag": "Busca RAG",
    "banco": "Consulta ao banco",
    "tecnicos": "Roteador",
    "auditoria": "Auditor",
}
SUMMARY_MAX = 200
METADATA_MAX_CHARS = 2000
# Chaves de metadata que nunca são gravadas, qualquer que seja o valor.
_FORBIDDEN_KEY = re.compile(
    r"pass|senha|secret|token|api[_-]?key|authorization|cookie|cpf|cnpj|card|cartao|cartão|hash",
    re.IGNORECASE,
)

_pending: set[asyncio.Task[None]] = set()


def is_enabled() -> bool:
    return get_settings().escritorio_virtual_enabled


@asynccontextmanager
async def _open_session() -> AsyncIterator[AsyncSession]:
    """Sessão própria do evento. Os testes trocam esta função para usar a sessão de teste."""
    async with get_sessionmaker()() as session:
        yield session


def sanitize_text(text: str, limit: int = SUMMARY_MAX) -> str:
    """Remove senhas, tokens, CPF e cartão, achata quebras de linha e corta no limite."""
    masked = mask_sensitive(" ".join(text.split())).text
    return masked if len(masked) <= limit else masked[: limit - 1] + "…"


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Só tipos simples; chaves sensíveis saem; textos passam pelo mascaramento."""

    def clean(value: Any, depth: int = 0) -> Any:
        if isinstance(value, bool) or value is None or isinstance(value, int | float):
            return value
        if isinstance(value, str):
            return sanitize_text(value, 160)
        if isinstance(value, uuid.UUID):
            return str(value)
        if depth >= 2:
            return None
        if isinstance(value, dict):
            return {
                str(k)[:40]: clean(v, depth + 1)
                for k, v in value.items()
                if not _FORBIDDEN_KEY.search(str(k))
            }
        if isinstance(value, list | tuple):
            return [clean(v, depth + 1) for v in list(value)[:20]]
        return None

    cleaned = clean(metadata or {})
    if not isinstance(cleaned, dict):
        return {}
    # Teto de tamanho: metadata grande demais é descartada, não truncada no meio.
    return cleaned if len(str(cleaned)) <= METADATA_MAX_CHARS else {"truncated": True}


def sql_metadata(table: str, statement: str) -> dict[str, str]:
    """Consulta ao banco: guarda só o nome da tabela e a query parametrizada, sem valores."""
    return {"table": table[:60], "query": " ".join(statement.split())[:300]}


def build_event(
    *,
    room: str,
    action: str,
    summary: str,
    agent_name: str | None = None,
    ticket_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> AgentEvent:
    if room not in ROOMS:
        raise ValueError(f"sala desconhecida: {room}")
    return AgentEvent(
        ticket_id=ticket_id,
        conversation_id=conversation_id,
        room=room,
        agent_name=(agent_name or AGENT_BY_ROOM[room])[:60],
        action=action[:40],
        summary=sanitize_text(summary),
        event_metadata=sanitize_metadata(metadata),
        user_id=user_id,
        # Horário no momento da emissão: a gravação é assíncrona e a ordem não pode depender dela.
        created_at=created_at or datetime.now(UTC),
    )


async def persist_event(event: AgentEvent) -> None:
    async with _open_session() as session:
        session.add(event)
        await session.commit()


async def _persist_quietly(event: AgentEvent) -> None:
    try:
        await persist_event(event)
    except Exception:  # o escritório nunca pode atrapalhar o atendimento
        log.warning("Não foi possível gravar o evento %s", event.action, exc_info=True)


def emit_agent_event(
    *,
    room: str,
    action: str,
    summary: str,
    agent_name: str | None = None,
    ticket_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Registra um passo de um agente. Segura para chamar em qualquer ponto do fluxo."""
    try:
        if not is_enabled():
            return
        event = build_event(
            room=room,
            action=action,
            summary=summary,
            agent_name=agent_name,
            ticket_id=ticket_id,
            conversation_id=conversation_id,
            user_id=user_id,
            metadata=metadata,
        )
        task = asyncio.get_running_loop().create_task(_persist_quietly(event))
        _pending.add(task)
        task.add_done_callback(_pending.discard)
    except Exception:
        log.warning("Evento do escritório descartado", exc_info=True)


async def flush_pending() -> None:
    """Espera as gravações em andamento (testes e desligamento)."""
    while _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)
