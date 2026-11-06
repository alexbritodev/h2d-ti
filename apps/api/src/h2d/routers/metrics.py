"""Números do dashboard. Técnico e administrador só leem; nenhuma rota aqui altera dados."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from h2d.deps import SessionDep, require_role
from h2d.metrics import MAX_DAYS, Overview, overview
from h2d.models import Role, User

StaffActor = Annotated[User, Depends(require_role(Role.TECH, Role.ADMIN))]

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview", operation_id="getMetricsOverview")
async def get_overview(
    session: SessionDep, _: StaffActor, days: Annotated[int, Query(ge=1, le=MAX_DAYS)] = 30
) -> Overview:
    return await overview(session, days)
