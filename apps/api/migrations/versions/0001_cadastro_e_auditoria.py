"""cadastro e auditoria

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Já criadas pelo init do banco, com superusuário; aqui só garante que existem.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skills")),
        sa.UniqueConstraint("name", name=op.f("uq_skills_name")),
    )
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sla_policies")),
        sa.UniqueConstraint("name", name=op.f("uq_sla_policies_name")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Enum("user", "tech", "admin", name="user_role"), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("is_vip", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_log_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False)
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("default_skill_id", sa.Uuid(), nullable=True),
        sa.Column("sla_policy_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["default_skill_id"], ["skills.id"], name=op.f("fk_categories_default_skill_id_skills")
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"], name=op.f("fk_categories_parent_id_categories")
        ),
        sa.ForeignKeyConstraint(
            ["sla_policy_id"],
            ["sla_policies.id"],
            name=op.f("fk_categories_sla_policy_id_sla_policies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint(
            "parent_id",
            "name",
            name=op.f("uq_categories_parent_id"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_table(
        "sla_targets",
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column(
            "priority", sa.Enum("P1", "P2", "P3", "P4", name="ticket_priority"), nullable=False
        ),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "first_response_minutes > 0", name=op.f("ck_sla_targets_first_response_positive")
        ),
        sa.CheckConstraint(
            "resolution_minutes >= first_response_minutes",
            name=op.f("ck_sla_targets_resolution_after_first_response"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["sla_policies.id"],
            name=op.f("fk_sla_targets_policy_id_sla_policies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("policy_id", "priority", name=op.f("pk_sla_targets")),
    )
    op.create_table(
        "technicians",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("max_capacity", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column(
            "schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("max_capacity > 0", name=op.f("ck_technicians_max_capacity_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_technicians_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_technicians")),
        sa.UniqueConstraint("user_id", name=op.f("uq_technicians_user_id")),
    )
    op.create_table(
        "technician_skills",
        sa.Column("technician_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
            name=op.f("fk_technician_skills_skill_id_skills"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technician_id"],
            ["technicians.id"],
            name=op.f("fk_technician_skills_technician_id_technicians"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("technician_id", "skill_id", name=op.f("pk_technician_skills")),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("technician_skills")
    op.drop_table("technicians")
    op.drop_table("sla_targets")
    op.drop_table("categories")
    op.drop_index(op.f("ix_audit_log_actor_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("sla_policies")
    op.drop_table("skills")
    op.execute("DROP TYPE ticket_priority")
    op.execute("DROP TYPE user_role")
