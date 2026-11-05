import os
from collections.abc import AsyncIterator
from pathlib import Path

# Precisa vir antes de qualquer import de h2d: as configurações são lidas uma vez só.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://h2d:h2d@localhost:5433/h2d_test"
)
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET"] = "segredo-de-teste-com-mais-de-32-caracteres"
os.environ["COOKIE_SECURE"] = "true"
os.environ["SEED_PASSWORD"] = "senha-de-teste-do-seed"

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from h2d.db import get_session  # noqa: E402
from h2d.main import create_app  # noqa: E402
from h2d.models import Role, User  # noqa: E402
from h2d.security import hash_password  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "senha-correta-de-teste"


def alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    return config


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    # Trava de segurança: os testes nunca rodam fora de um banco próprio para isso.
    database = make_url(TEST_DATABASE_URL).database or ""
    if not database.endswith("_test"):
        pytest.exit(f"Banco de teste precisa terminar em _test, recebido: {database}", 1)
    command.upgrade(alembic_config(), "head")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Cada teste roda numa transação desfeita ao final, sem deixar rastro no banco."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as db_session:
            yield db_session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def app(session: AsyncSession):
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_session] = override_session
    return application


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    # https: o cookie da sessão é Secure.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def make_user(session: AsyncSession):
    async def factory(
        email: str = "pessoa@h2d.local", role: Role = Role.USER, is_active: bool = True
    ) -> User:
        user = User(
            name="Pessoa de Teste",
            email=email,
            password_hash=hash_password(PASSWORD),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        await session.flush()
        return user

    return factory
