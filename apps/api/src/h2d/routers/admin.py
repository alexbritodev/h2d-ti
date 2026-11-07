"""Leituras do painel de administração e o ajuste de triagem. Tudo exige administrador."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from h2d.deps import SessionDep, require_role
from h2d.models import (
    AppSetting,
    AuditLog,
    Category,
    Priority,
    PromptVersion,
    Role,
    Skill,
    SlaPolicy,
    SlaTarget,
    User,
)
from h2d.tickets.service import DEFAULT_CONFIDENCE_THRESHOLD, get_setting

AdminActor = Annotated[User, Depends(require_role(Role.ADMIN))]

router = APIRouter(prefix="/admin", tags=["admin"])

THRESHOLD_KEY = "classification_confidence_threshold"
PRIORITY_ORDER = {Priority.P1: 1, Priority.P2: 2, Priority.P3: 3, Priority.P4: 4}


class AuditEntry(BaseModel):
    id: uuid.UUID
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: str | None
    # Nome legível do item (e-mail do usuário, por exemplo), quando o registro guarda um.
    entity_label: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_name: str | None
    children: int
    skill: str | None
    sla_policy: str | None
    is_active: bool


class SlaRow(BaseModel):
    policy: str
    priority: Priority
    first_response_minutes: int
    resolution_minutes: int


class PromptOut(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    is_active: bool
    created_at: datetime


class TriageSettings(BaseModel):
    confidence_threshold: float = Field(ge=0, le=1)


def _label(entry: AuditLog) -> str | None:
    for snapshot in (entry.after, entry.before):
        for key in ("email", "title", "filename"):
            if snapshot and isinstance(snapshot.get(key), str):
                return snapshot[key]
    return None


@router.get("/audit", operation_id="listAudit")
async def list_audit(
    session: SessionDep, _: AdminActor, limit: Annotated[int, Query(ge=1, le=500)] = 200
) -> list[AuditEntry]:
    rows = (
        await session.execute(
            select(AuditLog, User.name)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id)
            .limit(limit)
        )
    ).all()
    return [
        AuditEntry(
            id=entry.id,
            actor_name=name,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            entity_label=_label(entry),
            before=entry.before,
            after=entry.after,
            created_at=entry.created_at,
        )
        for entry, name in rows
    ]


@router.get("/categories", operation_id="listCategories")
async def list_categories(session: SessionDep, _: AdminActor) -> list[CategoryOut]:
    parent = aliased(Category)
    children = (
        select(Category.parent_id, func.count().label("total"))
        .where(Category.parent_id.is_not(None))
        .group_by(Category.parent_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Category, parent.name, Skill.name, SlaPolicy.name, children.c.total)
            .outerjoin(parent, parent.id == Category.parent_id)
            .outerjoin(Skill, Skill.id == Category.default_skill_id)
            .outerjoin(SlaPolicy, SlaPolicy.id == Category.sla_policy_id)
            .outerjoin(children, children.c.parent_id == Category.id)
            .order_by(
                func.lower(func.coalesce(parent.name, Category.name)),
                Category.parent_id.is_not(None),
                func.lower(Category.name),
            )
        )
    ).all()
    return [
        CategoryOut(
            id=category.id,
            name=category.name,
            parent_name=parent_name,
            children=total or 0,
            skill=skill,
            sla_policy=policy,
            is_active=category.is_active,
        )
        for category, parent_name, skill, policy, total in rows
    ]


@router.get("/sla", operation_id="listSlaTargets")
async def list_sla(session: SessionDep, _: AdminActor) -> list[SlaRow]:
    rows = (
        await session.execute(
            select(SlaPolicy.name, SlaTarget).join(SlaTarget, SlaTarget.policy_id == SlaPolicy.id)
        )
    ).all()
    result = [
        SlaRow(
            policy=name,
            priority=target.priority,
            first_response_minutes=target.first_response_minutes,
            resolution_minutes=target.resolution_minutes,
        )
        for name, target in rows
    ]
    return sorted(result, key=lambda r: (r.policy.lower(), PRIORITY_ORDER[r.priority]))


@router.get("/prompts", operation_id="listPromptVersions")
async def list_prompts(session: SessionDep, _: AdminActor) -> list[PromptOut]:
    rows = await session.scalars(
        select(PromptVersion).order_by(PromptVersion.name, PromptVersion.version.desc())
    )
    return [PromptOut.model_validate(row, from_attributes=True) for row in rows]


@router.get("/settings", operation_id="getTriageSettings")
async def get_triage_settings(session: SessionDep, _: AdminActor) -> TriageSettings:
    value = await get_setting(session, THRESHOLD_KEY, DEFAULT_CONFIDENCE_THRESHOLD)
    return TriageSettings(confidence_threshold=float(value))


@router.put("/settings", operation_id="updateTriageSettings")
async def update_triage_settings(
    body: TriageSettings, session: SessionDep, actor: AdminActor
) -> TriageSettings:
    row = await session.get(AppSetting, THRESHOLD_KEY)
    before = {"confidence_threshold": float(row.value)} if row is not None else None
    if row is None:
        session.add(AppSetting(key=THRESHOLD_KEY, value=body.confidence_threshold))
    else:
        row.value = body.confidence_threshold
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="settings.update",
            entity_type="setting",
            entity_id=THRESHOLD_KEY,
            before=before,
            after={"confidence_threshold": body.confidence_threshold},
        )
    )
    await session.commit()
    return body
