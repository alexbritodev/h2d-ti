"""Regras de chamado em código puro: prioridade, SLA e roteamento.

Sem banco e sem modelo de linguagem, então cada regra é testável sozinha e qualquer pessoa consegue
ver por que um chamado caiu com aquele técnico (o motivo vai para a linha do tempo).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from h2d.models import Level, Priority

# Linhas: impacto. Colunas: urgência (alta, média, baixa).
_MATRIX: dict[Level, dict[Level, Priority]] = {
    Level.HIGH: {Level.HIGH: Priority.P1, Level.MEDIUM: Priority.P2, Level.LOW: Priority.P3},
    Level.MEDIUM: {Level.HIGH: Priority.P2, Level.MEDIUM: Priority.P3, Level.LOW: Priority.P4},
    Level.LOW: {Level.HIGH: Priority.P3, Level.MEDIUM: Priority.P4, Level.LOW: Priority.P4},
}


def priority_from(impact: Level, urgency: Level) -> Priority:
    """A prioridade nunca vem do modelo de linguagem: vem desta matriz."""
    return _MATRIX[impact][urgency]


# --- SLA ----------------------------------------------------------------------------------------

AT_RISK_FROM = 0.75  # a partir de 75% do prazo gasto o chamado está em risco

SlaState = Literal["ok", "at_risk", "breached", "met"]


def sla_due(created_at: datetime, minutes: int) -> datetime:
    """Prazo em minutos corridos. Horário comercial entra como melhoria, se o time pedir."""
    return created_at + timedelta(minutes=minutes)


def sla_state(
    *, created_at: datetime, due: datetime | None, now: datetime, done_at: datetime | None = None
) -> SlaState:
    if due is None:
        return "ok"
    if done_at is not None:
        return "met" if done_at <= due else "breached"
    if now >= due:
        return "breached"
    total = (due - created_at).total_seconds()
    if total > 0 and (now - created_at).total_seconds() / total >= AT_RISK_FROM:
        return "at_risk"
    return "ok"


# --- Roteamento ---------------------------------------------------------------------------------

# Peso de cada chamado aberto na carga do técnico: um P1 pesa mais que vários P4.
PRIORITY_WEIGHT: dict[Priority, int] = {
    Priority.P1: 8,
    Priority.P2: 4,
    Priority.P3: 2,
    Priority.P4: 1,
}

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class Candidate:
    technician_id: uuid.UUID
    skill_ids: frozenset[uuid.UUID]
    is_available: bool
    max_capacity: int
    open_count: int
    open_weight: int
    schedule: dict[str, Any] = field(default_factory=dict)
    last_assigned_at: datetime | None = None


@dataclass(frozen=True)
class Decision:
    technician_id: uuid.UUID | None
    reason: str
    manual_triage: bool
    notify_leader: bool = False


def in_schedule(schedule: dict[str, Any], now: datetime, timezone: str) -> bool:
    """Agenda vazia significa sem restrição. Dia sem entrada na agenda é folga."""
    if not schedule:
        return True
    local = now.astimezone(ZoneInfo(timezone))
    window = schedule.get(_WEEKDAYS[local.weekday()])
    if not window or len(window) != 2:
        return False
    return str(window[0]) <= local.strftime("%H:%M") < str(window[1])


def route(
    candidates: list[Candidate],
    *,
    required_skill_id: uuid.UUID | None,
    priority: Priority | None,
    confidence: float | None,
    threshold: float,
    now: datetime,
    timezone: str = "America/Sao_Paulo",
) -> Decision:
    """Escolhe o técnico: habilidade, disponibilidade, capacidade e menor carga ponderada."""
    notify = priority is Priority.P1
    if confidence is None or priority is None:
        return Decision(None, "Chamado sem classificação: vai para a triagem manual", True, notify)
    if confidence < threshold:
        return Decision(
            None,
            f"Confiança da classificação ({confidence:.2f}) abaixo do limiar ({threshold:.2f})",
            True,
            notify,
        )

    with_skill = [
        c for c in candidates if required_skill_id is None or required_skill_id in c.skill_ids
    ]
    if not with_skill:
        return Decision(None, "Nenhum técnico tem a habilidade necessária", True, notify)
    available = [c for c in with_skill if c.is_available]
    if not available:
        return Decision(None, "Os técnicos com a habilidade estão indisponíveis", True, notify)
    on_shift = [c for c in available if in_schedule(c.schedule, now, timezone)]
    if not on_shift:
        return Decision(None, "Nenhum técnico com a habilidade está no horário agora", True, notify)
    with_room = [c for c in on_shift if c.open_count < c.max_capacity]
    if not with_room:
        return Decision(
            None, "Todos os técnicos elegíveis estão com a capacidade cheia", True, notify
        )

    # Menor carga ponderada. Empate: quem recebeu há mais tempo (rodízio); depois o id, para o
    # resultado ser sempre o mesmo.
    never = datetime.min.replace(tzinfo=now.tzinfo)
    chosen = min(
        with_room,
        key=lambda c: (c.open_weight, c.last_assigned_at or never, str(c.technician_id)),
    )
    tied = sum(1 for c in with_room if c.open_weight == chosen.open_weight)
    reason = (
        f"Menor carga ponderada ({chosen.open_weight}) entre {len(with_room)} técnicos elegíveis"
        + ("; empate resolvido por rodízio" if tied > 1 else "")
    )
    return Decision(chosen.technician_id, reason, False, notify)
