from fastapi import APIRouter, FastAPI

from h2d import __version__
from h2d.config import get_settings
from h2d.routers import auth, health, users


def create_app() -> FastAPI:
    # A documentação interativa não fica exposta em produção.
    is_production = get_settings().environment == "production"
    app = FastAPI(
        title="H2D - TI",
        version=__version__,
        docs_url=None if is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/api/openapi.json",
    )

    # Tudo sob /api: é o único prefixo que o Caddy encaminha à API.
    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(users.router)
    app.include_router(api)
    return app


app = create_app()
