from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.models import AuditLog, OutboxEvent, OutboxStatus, Role, User, UserInvite
from h2d.outbox import deliver_pending
from tests.conftest import PASSWORD

NEW = {"name": "Pessoa Convidada", "email": "Convidada@H2D.local ", "role": "user"}


async def _admin(client, make_user) -> User:
    admin = await make_user(email="chefe@h2d.local", role=Role.ADMIN)
    response = await client.post(
        "/api/auth/login", json={"email": "chefe@h2d.local", "password": PASSWORD}
    )
    assert response.status_code == 200
    return admin


async def _invite(client, session: AsyncSession) -> str:
    response = await client.post("/api/users/invite", json=NEW)
    assert response.status_code == 201
    event = await session.scalar(select(OutboxEvent).where(OutboxEvent.type == "user.invited"))
    assert event is not None
    return event.payload["token"]


async def test_so_admin_convida(client, make_user):
    await make_user(email="comum@h2d.local")
    await client.post("/api/auth/login", json={"email": "comum@h2d.local", "password": PASSWORD})
    assert (await client.post("/api/users/invite", json=NEW)).status_code == 403


async def test_convite_cria_conta_pendente_e_enfileira_o_email(
    client, make_user, session: AsyncSession
):
    admin = await _admin(client, make_user)

    response = await client.post("/api/users/invite", json=NEW)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "convidada@h2d.local"
    assert body["invite_pending"] is True
    event = await session.scalar(select(OutboxEvent).where(OutboxEvent.type == "user.invited"))
    assert event is not None
    assert event.payload["email"] == "convidada@h2d.local"
    assert event.payload["valid_hours"] >= 24
    # No banco fica só o hash do token, nunca o token.
    invite = await session.scalar(select(UserInvite))
    assert invite is not None and invite.token_hash != event.payload["token"]
    assert invite.expires_at - datetime.now(UTC) >= timedelta(hours=23, minutes=59)
    log = await session.scalar(select(AuditLog).where(AuditLog.action == "user.invite"))
    assert log is not None and log.actor_id == admin.id
    assert event.payload["token"] not in str(log.after)


async def test_email_repetido_no_convite_recebe_409(client, make_user):
    await _admin(client, make_user)
    await make_user(email="convidada@h2d.local")
    assert (await client.post("/api/users/invite", json=NEW)).status_code == 409


async def test_conta_convidada_nao_entra_sem_usar_o_link(client, make_user, session):
    await _admin(client, make_user)
    await _invite(client, session)
    client.cookies.clear()

    for senha in ("", "senha123", PASSWORD):
        login = await client.post(
            "/api/auth/login", json={"email": "convidada@h2d.local", "password": senha or "x"}
        )
        assert login.status_code == 401


async def test_link_define_a_senha_e_ja_entra(client, make_user, session):
    await _admin(client, make_user)
    token = await _invite(client, session)
    client.cookies.clear()

    info = await client.get(f"/api/auth/invite/{token}")
    assert info.status_code == 200
    assert info.json() == {"name": "Pessoa Convidada", "email": "convidada@h2d.local"}

    accepted = await client.post(f"/api/auth/invite/{token}", json={"password": "minha123"})
    assert accepted.status_code == 200
    assert (await client.get("/api/auth/me")).json()["email"] == "convidada@h2d.local"

    client.cookies.clear()
    login = await client.post(
        "/api/auth/login", json={"email": "convidada@h2d.local", "password": "minha123"}
    )
    assert login.status_code == 200


async def test_link_so_funciona_uma_vez(client, make_user, session):
    await _admin(client, make_user)
    token = await _invite(client, session)
    client.cookies.clear()

    assert (
        await client.post(f"/api/auth/invite/{token}", json={"password": "minha123"})
    ).status_code == 200
    assert (await client.get(f"/api/auth/invite/{token}")).status_code == 404
    again = await client.post(f"/api/auth/invite/{token}", json={"password": "outra123"})
    assert again.status_code == 404


async def test_senha_do_convite_segue_a_regra(client, make_user, session):
    await _admin(client, make_user)
    token = await _invite(client, session)
    client.cookies.clear()

    for senha in ("abc12", "somenteletras", "123456"):
        response = await client.post(f"/api/auth/invite/{token}", json={"password": senha})
        assert response.status_code == 422
    # Senha recusada não gasta o link.
    assert (await client.get(f"/api/auth/invite/{token}")).status_code == 200


async def test_link_vencido_ou_inventado_e_recusado(client, make_user, session: AsyncSession):
    await _admin(client, make_user)
    token = await _invite(client, session)
    client.cookies.clear()

    invite = await session.scalar(select(UserInvite))
    assert invite is not None
    invite.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    assert (await client.get(f"/api/auth/invite/{token}")).status_code == 404
    assert (
        await client.post(f"/api/auth/invite/{token}", json={"password": "minha123"})
    ).status_code == 404
    assert (await client.get("/api/auth/invite/inventado")).status_code == 404


async def test_link_vale_pelo_menos_24h(client, make_user, session: AsyncSession):
    await _admin(client, make_user)
    token = await _invite(client, session)
    client.cookies.clear()

    invite = await session.scalar(select(UserInvite))
    assert invite is not None
    invite.expires_at = datetime.now(UTC) + timedelta(hours=24)
    await session.commit()

    assert (await client.get(f"/api/auth/invite/{token}")).status_code == 200


async def test_reenvio_invalida_o_link_anterior(client, make_user, session: AsyncSession):
    await _admin(client, make_user)
    old = await _invite(client, session)
    user = await session.scalar(select(User).where(User.email == "convidada@h2d.local"))
    assert user is not None

    assert (await client.post(f"/api/users/{user.id}/invite")).status_code == 204

    events = list(
        await session.scalars(
            select(OutboxEvent).where(OutboxEvent.type == "user.invited").order_by(OutboxEvent.id)
        )
    )
    new = events[-1].payload["token"]
    assert new != old
    client.cookies.clear()
    assert (await client.get(f"/api/auth/invite/{old}")).status_code == 404
    assert (await client.get(f"/api/auth/invite/{new}")).status_code == 200


async def test_conta_desativada_nao_usa_o_link(client, make_user, session: AsyncSession):
    await _admin(client, make_user)
    token = await _invite(client, session)
    user = await session.scalar(select(User).where(User.email == "convidada@h2d.local"))
    assert user is not None
    user.is_active = False
    await session.commit()
    client.cookies.clear()

    assert (await client.get(f"/api/auth/invite/{token}")).status_code == 404


async def test_lista_mostra_convite_pendente_ate_o_uso(client, make_user, session):
    await _admin(client, make_user)
    token = await _invite(client, session)

    def pendente(users):
        return next(u for u in users if u["email"] == "convidada@h2d.local")["invite_pending"]

    assert pendente((await client.get("/api/users")).json()) is True
    await client.post(f"/api/auth/invite/{token}", json={"password": "minha123"})
    await client.post("/api/auth/login", json={"email": "chefe@h2d.local", "password": PASSWORD})
    assert pendente((await client.get("/api/users")).json()) is False


async def test_token_sai_do_evento_depois_da_entrega(client, make_user, session: AsyncSession):
    await _admin(client, make_user)
    await _invite(client, session)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await deliver_pending(session, http, url="http://n8n/x", secret="segredo")
    await session.commit()

    event = await session.scalar(select(OutboxEvent).where(OutboxEvent.type == "user.invited"))
    assert event is not None
    assert event.status is OutboxStatus.DELIVERED
    assert event.payload["token"] is None
    assert event.payload["email"] == "convidada@h2d.local"
