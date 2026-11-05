import uuid

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.db import get_session
from h2d.models import Category, Role, Skill, SlaPolicy, SlaTarget, Technician, User
from h2d.seed import CATEGORIES, SKILLS, TECHNICIANS, USERS, SeedNotAllowedError, run_seed
from tests.conftest import alembic_config


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_ready_com_banco_no_ar(client):
    assert (await client.get("/api/ready")).status_code == 200


async def test_ready_responde_503_sem_banco(app, client):
    class BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise OSError("banco fora do ar")

    async def broken():
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken

    response = await client.get("/api/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_migracoes_acompanham_os_modelos():
    # Falha se alguém mudou um modelo e esqueceu de gerar a migração.
    command.check(alembic_config())


async def test_extensoes_necessarias_instaladas(session: AsyncSession):
    installed = set(await session.scalars(text("SELECT extname FROM pg_extension")))
    assert {"vector", "pg_trgm"} <= installed


async def test_id_gerado_e_uuid_v7(make_user):
    user = await make_user()
    assert isinstance(user.id, uuid.UUID)
    assert user.id.version == 7


async def test_banco_recusa_email_com_maiuscula(session: AsyncSession):
    session.add(User(name="X", email="Maiuscula@h2d.local", password_hash="x", role=Role.USER))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_banco_recusa_categoria_raiz_duplicada(session: AsyncSession):
    session.add(Category(name="Repetida"))
    await session.flush()
    session.add(Category(name="Repetida"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_seed_cria_cadastros(session: AsyncSession):
    await run_seed(session)

    assert await session.scalar(select(func.count()).select_from(User)) == len(USERS)
    assert await session.scalar(select(func.count()).select_from(Skill)) == len(SKILLS)
    assert await session.scalar(select(func.count()).select_from(Technician)) == len(TECHNICIANS)
    assert await session.scalar(select(func.count()).select_from(SlaPolicy)) == 1
    assert await session.scalar(select(func.count()).select_from(SlaTarget)) == 4
    expected_categories = sum(1 + len(children) for _, children in CATEGORIES.values())
    assert await session.scalar(select(func.count()).select_from(Category)) == expected_categories


async def test_seed_pode_rodar_de_novo_sem_duplicar_nem_sobrescrever(session: AsyncSession):
    await run_seed(session)
    admin = await session.scalar(select(User).where(User.email == "admin@h2d.local"))
    assert admin is not None
    admin.name = "Nome alterado à mão"
    original_hash = admin.password_hash
    await session.flush()

    await run_seed(session)

    assert await session.scalar(select(func.count()).select_from(User)) == len(USERS)
    await session.refresh(admin)
    assert admin.name == "Nome alterado à mão"
    assert admin.password_hash == original_hash


async def test_todo_tecnico_do_seed_tem_papel_tech_e_toda_categoria_tem_quem_atenda(
    session: AsyncSession,
):
    await run_seed(session)

    for email in TECHNICIANS:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.role is Role.TECH

    # Sem isso, o roteador da F4 mandaria categorias inteiras para a triagem manual.
    covered = {skill for skills in TECHNICIANS.values() for skill in skills}
    assert {skill for skill, _ in CATEGORIES.values()} <= covered


async def test_login_com_usuario_do_seed(client, session: AsyncSession):
    await run_seed(session)
    password = get_settings().seed_password
    assert password is not None

    response = await client.post(
        "/api/auth/login",
        json={"email": "admin@h2d.local", "password": password.get_secret_value()},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_seed_recusa_producao(session: AsyncSession, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")

    with pytest.raises(SeedNotAllowedError):
        await run_seed(session)
