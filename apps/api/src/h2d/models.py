"""Grupo Cadastro e auditoria. Os demais grupos entram nas fases seguintes."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
