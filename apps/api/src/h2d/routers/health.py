import time
from typing import Literal

import httpx
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from h2d import __version__
from h2d.config import get_settings
from h2d.deps import SessionDep

router = APIRouter(tags=["operação"])

OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
OPENROUTER_CACHE_TTL_SECONDS = 60.0
OPENROUTER_TIMEOUT_SECONDS = 5.0

ServiceState = Literal["ok", "degraded", "unavailable"]


class HealthOut(BaseModel):
    status: str
    version: str


class ServiceStatusOut(BaseModel):
    status: ServiceState
    detail: str
    latency_ms: int | None = None


class SystemStatusOut(BaseModel):
    version: str
    backend: ServiceStatusOut
    database: ServiceStatusOut
    openrouter: ServiceStatusOut


_openrouter_cache: tuple[float, str, ServiceStatusOut] | None = None


def clear_status_cache() -> None:
    """Limpa o cache do status do OpenRouter (útil em testes)."""
    global _openrouter_cache
    _openrouter_cache = None


async def _check_database(session: SessionDep) -> ServiceStatusOut:
    started = time.monotonic()
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return ServiceStatusOut(status="unavailable", detail="Indisponível")
    latency_ms = max(0, round((time.monotonic() - started) * 1000))
    return ServiceStatusOut(status="ok", detail="Conectado", latency_ms=latency_ms)


async def _probe_key(
    url: str, headers: dict[str, str], invalid_statuses: set[int]
) -> ServiceStatusOut:
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError:
        return ServiceStatusOut(status="unavailable", detail="Sem conexão")

    latency_ms = max(0, round((time.monotonic() - started) * 1000))
    if response.status_code == 200:
        return ServiceStatusOut(status="ok", detail="Conectado", latency_ms=latency_ms)
    if response.status_code in invalid_statuses:
        return ServiceStatusOut(
            status="unavailable", detail="Chave inválida", latency_ms=latency_ms
        )
    if response.status_code == 429:
        return ServiceStatusOut(status="degraded", detail="Limite atingido", latency_ms=latency_ms)
    return ServiceStatusOut(
        status="unavailable",
        detail=f"HTTP {response.status_code}",
        latency_ms=latency_ms,
    )


async def _probe_openrouter(api_key: str) -> ServiceStatusOut:
    return await _probe_key(
        OPENROUTER_KEY_URL,
        {"Authorization": f"Bearer {api_key}"},
        {401, 403},
    )


async def _probe_gemini(api_key: str) -> ServiceStatusOut:
    return await _probe_key(
        f"{GEMINI_MODELS_URL}?pageSize=1",
        {"x-goog-api-key": api_key},
        {400, 401, 403},
    )


async def _check_openrouter() -> ServiceStatusOut:
    global _openrouter_cache
    settings = get_settings()
    gemini_secret = settings.gemini_api_key
    gemini_key = gemini_secret.get_secret_value().strip() if gemini_secret is not None else ""
    openrouter_secret = settings.openrouter_api_key
    openrouter_key = (
        openrouter_secret.get_secret_value().strip() if openrouter_secret is not None else ""
    )

    if gemini_key:
        provider, api_key = "gemini", gemini_key
    elif openrouter_key.startswith(("AIza", "AQ.")):
        provider, api_key = "gemini", openrouter_key
    elif openrouter_key:
        provider, api_key = "openrouter", openrouter_key
    else:
        return ServiceStatusOut(status="degraded", detail="Chave não configurada")

    cache_key = f"{provider}:{api_key}"
    now = time.monotonic()
    if _openrouter_cache is not None:
        cached_at, cached_key, cached_status = _openrouter_cache
        if cached_key == cache_key and (now - cached_at) < OPENROUTER_CACHE_TTL_SECONDS:
            return cached_status

    result = (
        await _probe_gemini(api_key) if provider == "gemini" else await _probe_openrouter(api_key)
    )
    _openrouter_cache = (now, cache_key, result)
    return result


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


@router.get("/status", operation_id="getSystemStatus")
async def system_status(session: SessionDep) -> SystemStatusOut:
    """Estado detalhado do backend, banco de dados e OpenRouter."""
    database = await _check_database(session)
    openrouter = await _check_openrouter()
    return SystemStatusOut(
        version=__version__,
        backend=ServiceStatusOut(status="ok", detail="Online"),
        database=database,
        openrouter=openrouter,
    )
