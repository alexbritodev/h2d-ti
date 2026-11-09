import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from h2d import __version__
from h2d.chat.service import get_prompt_version
from h2d.config import get_settings
from h2d.db import get_sessionmaker
from h2d.escritorio import router as escritorio
from h2d.kb.embeddings import embed_async, get_embedder
from h2d.routers import admin, auth, chat, health, hooks, kb, metrics, rag, tickets, users

log = logging.getLogger("h2d.api")


async def _warm_up_embedder() -> None:
    try:
        await embed_async(get_embedder(), ["aquecimento"])
    except Exception:  # o aquecimento é só uma ajuda; a busca carrega o modelo se precisar
        log.warning("Não foi possível aquecer o modelo de embeddings", exc_info=True)


async def _sync_prompt_version() -> None:
    """Registra a versão do prompt na subida, fora de qualquer pedido.

    Se isso rodasse no primeiro chat após um deploy, o UPDATE da versão ativa seguraria a
    transação aberta durante a chamada ao modelo e travaria os pedidos seguintes.
    """
    try:
        async with get_sessionmaker()() as session:
            await get_prompt_version(session)
            await session.commit()
    except Exception:  # o chat também cria a versão se faltar; aqui é só para não travar
        log.warning("Não foi possível registrar a versão do prompt", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await _sync_prompt_version()
    # Em produção o modelo carrega em segundo plano na subida: a primeira busca não espera.
    task = (
        asyncio.create_task(_warm_up_embedder())
        if get_settings().environment == "production"
        else None
    )
    yield
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    # A documentação interativa não fica exposta em produção.
    is_production = get_settings().environment == "production"
    app = FastAPI(
        title="H2D - TI",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/api/openapi.json",
    )

    # Tudo sob /api: é o único prefixo que o Caddy encaminha à API.
    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(users.router)
    api.include_router(admin.router)
    api.include_router(kb.router)
    api.include_router(rag.router)
    api.include_router(chat.router)
    api.include_router(tickets.router)
    api.include_router(metrics.router)
    api.include_router(hooks.router)
    # Escritório virtual (experimento): as rotas respondem 404 com a flag desligada.
    api.include_router(escritorio.router)
    api.include_router(escritorio.hooks_router)
    app.include_router(api)
    return app


app = create_app()
