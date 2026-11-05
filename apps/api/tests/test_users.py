import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.models import AuditLog, Role, User
from tests.conftest import PASSWORD

NEW_USER = {
    "name": "Pessoa Nova",
    "email": "Nova@H2D.local ",
    "password": "senha123",
    "role": "tech",
    "department": "Redes",
    "is_vip": False,
}


async def _login_as(client, make_user, role: Role, email: str = "chefe@h2d.local") -> User:
    user = await make_user(email=email, role=role)
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return user


@pytest.mark.parametrize("role", [Role.USER, Role.TECH])
async def test_so_administrador_acessa_usuarios(client, make_user, role):
    await _login_as(client, make_user, role)

    assert (await client.get("/api/users")).status_code == 403
    assert (await client.post("/api/users", json=NEW_USER)).status_code == 403
    assert (await client.patch(f"/api/users/{uuid.uuid4()}", json={"name": "X"})).status_code == 403
    reset = await client.post(f"/api/users/{uuid.uuid4()}/password", json={"password": "abc123"})
    assert reset.status_code == 403


async def test_sem_login_recebe_401(client):
    assert (await client.get("/api/users")).status_code == 401


async def test_admin_cria_usuario_que_consegue_entrar(client, make_user, session: AsyncSession):
    admin = await _login_as(client, make_user, Role.ADMIN)

    response = await client.post("/api/users", json=NEW_USER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "nova@h2d.local"
    assert body["role"] == "tech"
    assert "password" not in body and "password_hash" not in body

    # A pessoa nova entra com a senha definida pelo administrador.
    client.cookies.clear()
    login = await client.post(
        "/api/auth/login", json={"email": "nova@h2d.local", "password": "senha123"}
    )
    assert login.status_code == 200

    log = await session.scalar(select(AuditLog).where(AuditLog.action == "user.create"))
    assert log is not None
    assert log.actor_id == admin.id
    assert log.entity_id == body["id"]
    assert "password" not in str(log.after)


async def test_email_repetido_recebe_409(client, make_user):
    await _login_as(client, make_user, Role.ADMIN)
    await make_user(email="nova@h2d.local")

    response = await client.post("/api/users", json=NEW_USER)

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("password", "email"),
    [
        ("ab12", "nova@h2d.local"),  # curta
        ("abcdefgh", "nova@h2d.local"),  # sem número
        ("12345678", "nova@h2d.local"),  # sem letra
        ("senha123", "sem-arroba"),
        ("senha123", "a@semponto"),
    ],
)
async def test_dados_invalidos_recebem_422(client, make_user, password, email):
    await _login_as(client, make_user, Role.ADMIN)

    response = await client.post(
        "/api/users", json={**NEW_USER, "password": password, "email": email}
    )

    assert response.status_code == 422


async def test_lista_com_filtros(client, make_user):
    await _login_as(client, make_user, Role.ADMIN)
    await make_user(email="a@h2d.local", role=Role.TECH)
    await make_user(email="b@h2d.local", role=Role.USER, is_active=False)

    todos = (await client.get("/api/users")).json()
    tecnicos = (await client.get("/api/users", params={"role": "tech"})).json()
    inativos = (await client.get("/api/users", params={"status_filter": "inactive"})).json()

    assert {u["email"] for u in todos} >= {"chefe@h2d.local", "a@h2d.local", "b@h2d.local"}
    assert [u["email"] for u in tecnicos] == ["a@h2d.local"]
    assert [u["email"] for u in inativos] == ["b@h2d.local"]
    assert all("password_hash" not in u for u in todos)


async def test_admin_edita_usuario_e_audita_antes_e_depois(
    client, make_user, session: AsyncSession
):
    await _login_as(client, make_user, Role.ADMIN)
    alvo = await make_user(email="alvo@h2d.local")

    response = await client.patch(
        f"/api/users/{alvo.id}", json={"role": "tech", "department": "  TI ", "is_vip": True}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["role"], body["department"], body["is_vip"]) == ("tech", "TI", True)
    log = await session.scalar(select(AuditLog).where(AuditLog.action == "user.update"))
    assert log is not None
    assert log.before is not None and log.after is not None
    assert log.before["role"] == "user"
    assert log.after["role"] == "tech"


async def test_desativar_vale_na_hora(client, make_user):
    await _login_as(client, make_user, Role.ADMIN)
    alvo = await make_user(email="alvo@h2d.local")

    await client.patch(f"/api/users/{alvo.id}", json={"is_active": False})

    client.cookies.clear()
    login = await client.post(
        "/api/auth/login", json={"email": "alvo@h2d.local", "password": PASSWORD}
    )
    assert login.status_code == 401


async def test_admin_nao_remove_o_proprio_acesso(client, make_user):
    admin = await _login_as(client, make_user, Role.ADMIN)

    desativar = await client.patch(f"/api/users/{admin.id}", json={"is_active": False})
    rebaixar = await client.patch(f"/api/users/{admin.id}", json={"role": "user"})
    mesmo_cargo = await client.patch(f"/api/users/{admin.id}", json={"department": "TI"})

    assert desativar.status_code == 409
    assert rebaixar.status_code == 409
    assert mesmo_cargo.status_code == 200


async def test_edita_usuario_inexistente_recebe_404(client, make_user):
    await _login_as(client, make_user, Role.ADMIN)

    response = await client.patch(f"/api/users/{uuid.uuid4()}", json={"name": "X"})

    assert response.status_code == 404


async def test_redefinir_senha_troca_a_senha_sem_gravar_na_auditoria(
    client, make_user, session: AsyncSession
):
    await _login_as(client, make_user, Role.ADMIN)
    alvo = await make_user(email="alvo@h2d.local")

    response = await client.post(f"/api/users/{alvo.id}/password", json={"password": "outra456"})

    assert response.status_code == 204
    client.cookies.clear()
    antiga = await client.post(
        "/api/auth/login", json={"email": "alvo@h2d.local", "password": PASSWORD}
    )
    nova = await client.post(
        "/api/auth/login", json={"email": "alvo@h2d.local", "password": "outra456"}
    )
    assert (antiga.status_code, nova.status_code) == (401, 200)
    log = await session.scalar(select(AuditLog).where(AuditLog.action == "user.password_reset"))
    assert log is not None
    assert log.before is None and log.after is None


async def test_redefinir_senha_recusa_senha_fraca(client, make_user):
    await _login_as(client, make_user, Role.ADMIN)
    alvo = await make_user(email="alvo@h2d.local")

    response = await client.post(f"/api/users/{alvo.id}/password", json={"password": "abcdef"})

    assert response.status_code == 422
