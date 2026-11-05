"""Grupos Cadastro, auditoria e Conhecimento. Os demais grupos entram nas fases seguintes."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from uuid_utils.compat import uuid7


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Role(StrEnum):
    USER = "user"
    TECH = "tech"
    ADMIN = "admin"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


def _enum(enum_class: type[StrEnum], name: str) -> Enum:
    return Enum(enum_class, name=name, values_callable=lambda e: [member.value for member in e])


def _id_column() -> Mapped[uuid.UUID]:
    # O PostgreSQL 17 não tem uuidv7() nativo, então o ID nasce na aplicação.
    return mapped_column(Uuid, primary_key=True, default=uuid7)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    id: Mapped[uuid.UUID] = _id_column()
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(_enum(Role, "user_role"), default=Role.USER)
    department: Mapped[str | None] = mapped_column(String(120))
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = _id_column()
    name: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = _created_at()


class Technician(Base):
    __tablename__ = "technicians"
    __table_args__ = (CheckConstraint("max_capacity > 0", name="max_capacity_positive"),)

    id: Mapped[uuid.UUID] = _id_column()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    max_capacity: Mapped[int] = mapped_column(Integer, default=10, server_default=text("10"))
    # Ex.: {"mon": ["08:00", "18:00"], "tue": ["08:00", "18:00"]}
    schedule: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    user: Mapped[User] = relationship()
    skills: Mapped[list[Skill]] = relationship(secondary="technician_skills")


class TechnicianSkill(Base):
    __tablename__ = "technician_skills"

    technician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("technicians.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id: Mapped[uuid.UUID] = _id_column()
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    targets: Mapped[list["SlaTarget"]] = relationship(cascade="all, delete-orphan")


class SlaTarget(Base):
    """Prazos de uma política para cada prioridade."""

    __tablename__ = "sla_targets"
    __table_args__ = (
        CheckConstraint("first_response_minutes > 0", name="first_response_positive"),
        CheckConstraint(
            "resolution_minutes >= first_response_minutes", name="resolution_after_first_response"
        ),
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sla_policies.id", ondelete="CASCADE"), primary_key=True
    )
    priority: Mapped[Priority] = mapped_column(_enum(Priority, "ticket_priority"), primary_key=True)
    first_response_minutes: Mapped[int] = mapped_column(Integer)
    resolution_minutes: Mapped[int] = mapped_column(Integer)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("parent_id", "name", postgresql_nulls_not_distinct=True),)

    id: Mapped[uuid.UUID] = _id_column()
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    default_skill_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("skills.id"))
    sla_policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sla_policies.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _id_column()
    # Sem cascata: o histórico sobrevive mesmo se o ator for removido.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()


# --- Conhecimento (F2) --------------------------------------------------------------------------

# Dimensão do modelo de embeddings (ADR-003). Mudar exige migração.
EMBEDDING_DIM = 384
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Visibility(StrEnum):
    PUBLIC = "public"
    IT = "it"


class VersionStatus(StrEnum):
    PROCESSING = "processing"
    ACTIVE = "active"
    ARCHIVED = "archived"
    FAILED = "failed"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class KbDocument(Base):
    """Documento lógico. Cada envio de arquivo vira uma versão dele."""

    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = _id_column()
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(120))
    visibility: Mapped[Visibility] = mapped_column(
        _enum(Visibility, "kb_visibility"), default=Visibility.PUBLIC
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    valid_until: Mapped[datetime | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    versions: Mapped[list["KbDocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KbDocumentVersion(Base):
    """Cada upload. Só uma versão por documento fica ativa; as anteriores são arquivadas."""

    __tablename__ = "kb_document_versions"
    __table_args__ = (
        # O mesmo arquivo (mesmo hash) não é processado de novo dentro do documento.
        UniqueConstraint("document_id", "sha256", name="uq_kb_document_versions_document_sha"),
        Index(
            "uq_kb_document_versions_one_active",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = _id_column()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    # Caminho do arquivo original no volume de uploads.
    file_path: Mapped[str] = mapped_column(Text)
    status: Mapped[VersionStatus] = mapped_column(
        _enum(VersionStatus, "kb_version_status"), default=VersionStatus.PROCESSING
    )
    markdown: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created_at()
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[KbDocument] = relationship(back_populates="versions")


class KbChunk(Base):
    """Trecho pesquisável. A visibilidade é copiada do documento para o filtro rodar na consulta."""

    __tablename__ = "kb_chunks"
    __table_args__ = (
        Index(
            "ix_kb_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_kb_chunks_tsv", "tsv", postgresql_using="gin"),
        UniqueConstraint("version_id", "position", name="uq_kb_chunks_version_position"),
    )

    id: Mapped[uuid.UUID] = _id_column()
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_document_versions.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Caminho de títulos até o trecho, para a citação.
    breadcrumb: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str] = mapped_column(String(200), default=EMBEDDING_MODEL)
    # O caminho de títulos entra na busca por palavras, junto com o texto do trecho.
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('portuguese', breadcrumb || ' ' || content)", persisted=True),
    )
    visibility: Mapped[Visibility] = mapped_column(_enum(Visibility, "kb_visibility"))
    created_at: Mapped[datetime] = _created_at()


class IngestionJob(Base):
    """Histórico e estado do processamento de uma versão."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = _id_column()
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_document_versions.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[JobState] = mapped_column(
        _enum(JobState, "ingestion_state"), default=JobState.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
