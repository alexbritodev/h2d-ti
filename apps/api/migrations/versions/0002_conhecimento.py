"""conhecimento

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False: o tipo kb_visibility é usado por duas tabelas e é criado uma vez só, abaixo.
VISIBILITY = postgresql.ENUM("public", "it", name="kb_visibility", create_type=False)
VERSION_STATUS = postgresql.ENUM(
    "processing", "active", "archived", "failed", name="kb_version_status", create_type=False
)
JOB_STATE = postgresql.ENUM(
    "queued", "running", "succeeded", "failed", name="ingestion_state", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    VISIBILITY.create(bind)
    VERSION_STATUS.create(bind)
    JOB_STATE.create(bind)
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("source", sa.String(length=300), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("visibility", VISIBILITY, nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
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
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_kb_documents_owner_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_documents")),
    )
    op.create_table(
        "kb_document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=300), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("status", VERSION_STATUS, nullable=False),
        sa.Column("markdown", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_kb_document_versions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["kb_documents.id"],
            name=op.f("fk_kb_document_versions_document_id_kb_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_document_versions")),
        sa.UniqueConstraint("document_id", "sha256", name="uq_kb_document_versions_document_sha"),
    )
    op.create_index(
        op.f("ix_kb_document_versions_document_id"),
        "kb_document_versions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "uq_kb_document_versions_one_active",
        "kb_document_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("state", JOB_STATE, nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["kb_document_versions.id"],
            name=op.f("fk_ingestion_jobs_version_id_kb_document_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_jobs")),
    )
    op.create_index(
        op.f("ix_ingestion_jobs_version_id"), "ingestion_jobs", ["version_id"], unique=False
    )
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("breadcrumb", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=False),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('portuguese', breadcrumb || ' ' || content)", persisted=True),
            nullable=False,
        ),
        sa.Column("visibility", VISIBILITY, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["kb_documents.id"],
            name=op.f("fk_kb_chunks_document_id_kb_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["kb_document_versions.id"],
            name=op.f("fk_kb_chunks_version_id_kb_document_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_chunks")),
        sa.UniqueConstraint("version_id", "position", name="uq_kb_chunks_version_position"),
    )
    op.create_index(op.f("ix_kb_chunks_document_id"), "kb_chunks", ["document_id"], unique=False)
    op.create_index(
        "ix_kb_chunks_embedding_hnsw",
        "kb_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_kb_chunks_tsv", "kb_chunks", ["tsv"], unique=False, postgresql_using="gin")
    op.create_index(op.f("ix_kb_chunks_version_id"), "kb_chunks", ["version_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_kb_chunks_version_id"), table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_tsv", table_name="kb_chunks", postgresql_using="gin")
    op.drop_index(
        "ix_kb_chunks_embedding_hnsw",
        table_name="kb_chunks",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index(op.f("ix_kb_chunks_document_id"), table_name="kb_chunks")
    op.drop_table("kb_chunks")
    op.drop_index(op.f("ix_ingestion_jobs_version_id"), table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index(
        "uq_kb_document_versions_one_active",
        table_name="kb_document_versions",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(op.f("ix_kb_document_versions_document_id"), table_name="kb_document_versions")
    op.drop_table("kb_document_versions")
    op.drop_table("kb_documents")
    bind = op.get_bind()
    JOB_STATE.drop(bind)
    VERSION_STATUS.drop(bind)
    VISIBILITY.drop(bind)
