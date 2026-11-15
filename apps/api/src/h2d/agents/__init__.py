"""Módulo de Agentes Inteligentes do H2D-TI.

Agente 1: Guardião de Entrada (filtro rápido e semântico de conteúdo impróprio).
Agente 2: Validador de Resposta (juiz anti-alucinação e conferência de fidelidade).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from h2d.agents.guardiao import GUARDIAO_BLOCKED_MESSAGE, Guardiao, GuardiaoResult
from h2d.agents.validador import (
    NOT_FOUND_MANUALS_MESSAGE,
    REGENERATE_RESTRICTIVE_PROMPT,
    Validador,
    ValidadorResult,
)

AgentName = Literal["guardiao", "rag", "llm", "validador"]
AgentStatus = Literal["aguardando", "em_andamento", "aprovado", "reprovado", "erro"]


@dataclass
class AgentProgressEvent:
    agente: AgentName
    status: AgentStatus
    mensagem: str
    detalhes: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "agente": self.agente,
            "status": self.status,
            "mensagem": self.mensagem,
            "detalhes": self.detalhes,
            "timestamp": self.timestamp,
        }


__all__ = [
    "GUARDIAO_BLOCKED_MESSAGE",
    "NOT_FOUND_MANUALS_MESSAGE",
    "REGENERATE_RESTRICTIVE_PROMPT",
    "AgentName",
    "AgentProgressEvent",
    "AgentStatus",
    "Guardiao",
    "GuardiaoResult",
    "Validador",
    "ValidadorResult",
]
