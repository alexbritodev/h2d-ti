"""escritório virtual: eventos dos agentes (somente aditiva)

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("room", sa.String(length=20), nullable=False),
        sa.Column("agent_name", sa.String(length=60), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=200), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_events")),
    )
    op.create_index("ix_agent_events_created_at", "agent_events", ["created_at"])
    op.create_index(
        "ix_agent_events_ticket_id_created_at", "agent_events", ["ticket_id", "created_at"]
    )
    op.create_index(
        "ix_agent_events_conversation_id_created_at",
        "agent_events",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_events_conversation_id_created_at", table_name="agent_events")
    op.drop_index("ix_agent_events_ticket_id_created_at", table_name="agent_events")
    op.drop_index("ix_agent_events_created_at", table_name="agent_events")
    op.drop_table("agent_events")
