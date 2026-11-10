"""Chamados do sistema como fonte extra do chat, só para o administrador.

O chat de quem não é administrador nunca chama este módulo. Os chamados entram como fontes
numeradas (dados, não instruções), com o resumo geral primeiro e depois os chamados que casam com
a pergunta ou, se ela fala de chamados em geral, os mais recentes ainda abertos.
"""

import re
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from h2d.kb.search import Hit
from h2d.models import Category, Technician, Ticket, TicketStatus, User

TICKET_LIMIT = 5
TEXT_LIMIT = 400
STATUS_LABELS = {
    TicketStatus.NEW: "novo",
    TicketStatus.TRIAGE: "em triagem",
    TicketStatus.ASSIGNED: "atribuído",
    TicketStatus.IN_PROGRESS: "em andamento",
    TicketStatus.WAITING_USER: "aguardando o usuário",
    TicketStatus.RESOLVED: "resolvido",
}
# Pergunta que fala de chamados em geral, sem palavra específica para buscar.
_GENERAL = re.compile(
    r"chamado|ticket|fila|abert|pendent|sla|atras|urgent|prioridade|t[eé]cnico|atribu",
    re.IGNORECASE,
)
_CODE = re.compile(r"h2d-?(\d{1,6})", re.IGNORECASE)
_STOPWORDS = frozenset(
    [
        "para",
        "como",
        "qual",
        "quais",
        "quem",
        "quando",
        "onde",
        "sobre",
        "isso",
        "esse",
        "essa",
        "estes",
        "estão",
        "está",
        "tem",
        "têm",
        "você",
        "voce",
        "sistema",
        "chamado",
        "chamados",
        "acesso",
        "consegue",
        "pode",
        "posso",
        "ajudar",
        "mostre",
        "liste",
    ]
)


def _clip(text: str | None, limit: int = TEXT_LIMIT) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _keywords(query: str) -> list[str]:
    words = re.findall(r"[^\W_]{4,}", query.lower())
    return [w for w in dict.fromkeys(words) if w not in _STOPWORDS][:6]


def _hit(identity: UUID, title: str, breadcrumb: str, content: str) -> Hit:
    return Hit(identity, identity, title, breadcrumb, content, "ti", 0.0, kind="ticket")


async def _overview(session: AsyncSession) -> Hit | None:
    rows = (
        await session.execute(select(Ticket.status, func.count()).group_by(Ticket.status))
    ).all()
    if not rows:
        return None
    total = sum(count for _, count in rows)
    by_status = ", ".join(
        f"{STATUS_LABELS.get(status, str(status))}: {count}" for status, count in rows
    )
    open_by_priority = (
        await session.execute(
            select(Ticket.priority, func.count())
            .where(Ticket.status != TicketStatus.RESOLVED)
            .group_by(Ticket.priority)
        )
    ).all()
    priorities = ", ".join(
        f"{priority.value if priority else 'sem prioridade'}: {count}"
        for priority, count in sorted(open_by_priority, key=lambda r: str(r[0]))
    )
    content = f"Total de chamados: {total}. Por situação: {by_status}."
    if priorities:
        content += f" Abertos por prioridade: {priorities}."
    return _hit(
        UUID(int=0),
        "Resumo dos chamados do sistema",
        "Chamados > Resumo",
        content,
    )


async def admin_ticket_sources(session: AsyncSession, query: str) -> list[Hit]:
    """Resumo geral e até TICKET_LIMIT chamados relevantes para a pergunta."""
    requester = aliased(User)
    technician_user = aliased(User)
    base = (
        select(Ticket, Category.name, requester.name, technician_user.name)
        .join(requester, requester.id == Ticket.requester_id)
        .outerjoin(Category, Category.id == Ticket.category_id)
        .outerjoin(Technician, Technician.id == Ticket.technician_id)
        .outerjoin(technician_user, technician_user.id == Technician.user_id)
        .order_by(Ticket.updated_at.desc())
        .limit(TICKET_LIMIT)
    )
    conditions = []
    for match in _CODE.finditer(query):
        conditions.append(Ticket.number == int(match.group(1)))
    for word in _keywords(query):
        like = f"%{word}%"
        conditions.append(or_(Ticket.summary.ilike(like), Ticket.description.ilike(like)))
        conditions.append(cast(Ticket.solution, String).ilike(like))
    rows = list((await session.execute(base.where(or_(*conditions)))).all()) if conditions else []
    if len(rows) < 3 and _GENERAL.search(query):
        seen = {row[0].id for row in rows}
        recent = (await session.execute(base.where(Ticket.status != TicketStatus.RESOLVED))).all()
        rows += [row for row in recent if row[0].id not in seen][: TICKET_LIMIT - len(rows)]

    hits: list[Hit] = []
    if overview := await _overview(session):
        hits.append(overview)
    for ticket, category, requester_name, technician_name in rows:
        status = STATUS_LABELS.get(ticket.status, str(ticket.status))
        parts = [
            f"Situação: {status}",
            f"Prioridade: {ticket.priority.value if ticket.priority else 'não definida'}",
            f"Categoria: {category or 'sem categoria'}",
            f"Solicitante: {requester_name}",
            f"Técnico: {technician_name or 'sem técnico'}",
            f"Aberto em {ticket.created_at:%d/%m/%Y}",
        ]
        if ticket.resolution_due and ticket.status is not TicketStatus.RESOLVED:
            parts.append(f"Prazo de resolução: {ticket.resolution_due:%d/%m/%Y %H:%M}")
        text = ". ".join(parts) + "."
        if ticket.description:
            text += f" Descrição: {_clip(ticket.description)}"
        if ticket.solution:
            text += f" Solução: {_clip(ticket.solution)}"
        hits.append(
            _hit(
                ticket.id,
                f"Chamado {ticket.code}: {_clip(ticket.summary, 120)}",
                f"Chamados > {status}",
                text,
            )
        )
    return hits
