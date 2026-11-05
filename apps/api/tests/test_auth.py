import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import Settings, get_settings
from h2d.deps import SESSION_COOKIE, require_role
from h2d.models import Role
from h2d.security import create_session_token, read_session_token
from tests.conftest import PASSWORD


async def _login(client, email="pessoa@h2d.local", password=PASSWORD):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def test_login_devolve_usuario_sem_expor_hash(client, make_user):
    await make_user()

    response = await _login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "pessoa@h2d.local"
    assert body["role"] == "user"
    assert "password_hash" not in body


async def test_cookie_de_sessao_tem_atributos_de_seguranca(client, make_user):
    await make_user()

    response = await _login(client)

    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api" in cookie


async def test_email_nao_diferencia_maiusculas(client, make_user):
    await make_user()

    assert (await _login(client, email="  PESSOA@H2D.local ")).status_code == 200


async def test_falhas_de_login_sao_indistinguiveis(client, make_user):
    await make_user()
    await make_user(email="inativo@h2d.local", is_active=False)

    wrong_password = await _login(client, password="senha-errada")
    unknown_email = await _login(client, email="ninguem@h2d.local")
    inactive = await _login(client, email="inativo@h2d.local")

    for response in (wrong_password, unknown_email, inactive):
        assert response.status_code == 401
        assert "set-cookie" not in response.headers
    assert wrong_password.json() == unknown_email.json() == inactive.json()


async def test_me_exige_sessao(client):
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_me_com_sessao_valida(client, make_user):
    await make_user()
    await _login(client)

    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "pessoa@h2d.local"


async def test_me_recusa_token_assinado_com_outro_segredo(client, make_user):
    user = await make_user()
    forged = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(hours=1)},
        "outro-segredo-com-mais-de-32-caracteres-aqui",
        algorithm="HS256",
    )
    client.cookies.set(SESSION_COOKIE, forged, domain="testserver", path="/api")

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_me_recusa_token_expirado(client, make_user):
    user = await make_user()
    expired = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(seconds=1)},
        get_settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    client.cookies.set(SESSION_COOKIE, expired, domain="testserver", path="/api")

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_token_sem_algoritmo_nao_e_aceito(make_user):
    user = await make_user()
    unsigned = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(hours=1)},
        key="",
        algorithm="none",
    )

    assert read_session_token(unsigned) is None


async def test_desativar_usuario_derruba_sessao_na_hora(client, make_user, session: AsyncSession):
    user = await make_user()
    await _login(client)

    user.is_active = False
    await session.flush()

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_token_de_usuario_inexistente_e_recusado(client):
    token = create_session_token(uuid.uuid4())
    client.cookies.set(SESSION_COOKIE, token, domain="testserver", path="/api")

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_logout_remove_cookie(client, make_user):
    await make_user()
    await _login(client)

    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_require_role_separa_papeis(app, client, make_user):
    @app.get("/api/somente-admin")
    async def admin_only(user=Depends(require_role(Role.ADMIN))):  # noqa: B008
        return {"ok": True}

    await make_user(email="comum@h2d.local", role=Role.USER)
    await make_user(email="chefe@h2d.local", role=Role.ADMIN)

    assert (await client.get("/api/somente-admin")).status_code == 401

    await _login(client, email="comum@h2d.local")
    assert (await client.get("/api/somente-admin")).status_code == 403

    await client.post("/api/auth/logout")
    await _login(client, email="chefe@h2d.local")
    assert (await client.get("/api/somente-admin")).status_code == 200


def test_producao_exige_cookie_secure():
    try:
        Settings(
            environment="production",
            database_url="postgresql+asyncpg://x/y",
            jwt_secret="a" * 32,  # type: ignore[arg-type]
            cookie_secure=False,
        )
    except ValueError as error:
        assert "COOKIE_SECURE" in str(error)
    else:
        raise AssertionError("Deveria recusar produção sem cookie Secure")


def test_segredo_curto_e_recusado():
    try:
        Settings(database_url="postgresql+asyncpg://x/y", jwt_secret="curto")  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError("Deveria recusar JWT_SECRET curto")
