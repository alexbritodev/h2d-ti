from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from h2d import __version__
from h2d.deps import SessionDep

router = APIRouter(tags=["operação"])


class HealthOut(BaseModel):
    status: str
    version: str


@router.get("/health", operation_id="getHealth")
async def health() -> HealthOut:
    """O processo está de pé. Não toca em dependências."""
    return HealthOut(status="ok", version=__version__)


@router.get("/ready", operation_id="getReady")
async def ready(session: SessionDep, response: Response) -> HealthOut:
    """Pronto para atender: o banco responde. O deploy termina checando este endpoint."""
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="unavailable", version=__version__)
    return HealthOut(status="ok", version=__version__)
