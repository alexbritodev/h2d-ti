import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_utils.compat import uuid7

from h2d.models import Base


class AgentEvent(Base):
    """Um passo de um agente no atendimento, para a animação do escritório.

    Sem chaves estrangeiras de propósito: o evento é gravado fora da transação do atendimento
    (o chamado ainda pode não ter sido confirmado) e nunca pode derrubar o fluxo real.
    """

    __tablename__ = "agent_events"
    __table_args__ = (
        Index("ix_agent_events_ticket_id_created_at", "ticket_id", "created_at"),
        Index("ix_agent_events_conversation_id_created_at", "conversation_id", "created_at"),
        Index("ix_agent_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # recepcao | triagem | rag | banco | tecnicos | auditoria
    room: Mapped[str] = mapped_column(String(20))
    agent_name: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(String(200))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    # Dono do atendimento (quem pediu): define quem pode ver o evento.
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
