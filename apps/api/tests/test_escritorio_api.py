"""Fase 3: configuração, replay, SSE e webhook, com a autorização por perfil."""

import json
import time
import typing
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.escritorio import events, router
from h2d.escritorio.models import AgentEvent
from h2d.models import Role
from h2d.outbox import sign
from tests.conftest import PASSWORD
from tests.test_chat import _login

SEGREDO = "segredo-compartilhado-de-teste"


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "escritorio_virtual_enabled", True)


@pytest.fixture(autouse=True)
def stream_by_the_test_session(app, session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """O stream usa a sessão do teste e dura pouco: o transporte de teste não é incremental."""

    @asynccontextmanager
    async def shared():
        yield session

    app.dependency_overrides[router.get_session_factory] = lambda: shared
    monkeypatch.setattr(router, "POLL_SECONDS", 0.02)
    monkeypatch.setattr(router, "STREAM_MAX_SECONDS", 0.4)


async def add_event(
    session: AsyncSession,
    *,
    room: str = "recepcao",
    action: str = "mensagem_recebida",
    summary: str = "passo",
    user_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    ticket_id: uuid.UUID | None = None,
    at: datetime | None = None,
    metadata: dict | None = None,
) -> AgentEvent:
    event = events.build_event(
        room=room,
        action=action,
        summary=summary,
        user_id=user_id,
        conversation_id=conversation_id,
        ticket_id=ticket_id,
        created_at=at,
        metadata=metadata,
    )
    session.add(event)
    await session.flush()
    return event


async def login_as(client, make_user, role: Role, email: str):
    client.cookies.clear()
    return await _login(client, make_user, role=role, email=email)


def sse_events(text: str) -> list[dict]:
    parsed = []
    for block in text.strip().split("\n\n"):
        lines = [line for line in block.splitlines() if not line.startswith(":")]
        if not lines:
            continue
        data = next(line for line in lines if line.startswith("data: "))
        ident = next(line for line in lines if line.startswith("id: "))
        parsed.append({"id": ident.removeprefix("id: "), **json.loads(data.removeprefix("data: "))})
    return parsed


def signed(secret: str, body: dict) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    headers = {
        "X-H2D-Timestamp": ts,
        "X-H2D-Signature": sign(secret, ts, raw),
        "Content-Type": "application/json",
    }
    return raw, headers


def test_as_salas_da_api_e_do_webhook_sao_as_mesmas() -> None:
    assert set(typing.get_args(router.Room)) == set(events.ROOMS)


# ---------------------------------------------------------------- flag desligada


async def test_com_a_flag_desligada_tudo_responde_404_e_a_config_diz_desligado(
    client, make_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "escritorio_virtual_enabled", False)
    monkeypatch.setattr(get_settings(), "n8n_hmac_secret", SecretStr(SEGREDO))
    await login_as(client, make_user, Role.ADMIN, "admin@h2d.local")

    config = await client.get("/api/escritorio/config")
    assert config.status_code == 200
    assert config.json() == {"enabled": False, "demo": False}
    for path in ("atendimentos", "eventos", "stream"):
        assert (await client.get(f"/api/escritorio/{path}")).status_code == 404, path
    raw, headers = signed(
        SEGREDO, {"room": "rag", "action": "rag_busca", "summary": "busca", "metadata": {}}
    )
    hook = await client.post("/api/hooks/n8n/escritorio/events", content=raw, headers=headers)
    assert hook.status_code == 404


async def test_config_mostra_a_demo_so_quando_o_escritorio_esta_ligado(
    client, make_user, enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    await login_as(client, make_user, Role.USER, "pessoa@h2d.local")
    monkeypatch.setattr(get_settings(), "escritorio_virtual_demo", True)
    assert (await client.get("/api/escritorio/config")).json() == {"enabled": True, "demo": True}


async def test_sem_login_nao_ve_nada(client, enabled) -> None:
    for path in ("config", "atendimentos", "eventos", "stream"):
        assert (await client.get(f"/api/escritorio/{path}")).status_code == 401, path


# ---------------------------------------------------------------- permissões e replay


async def test_usuario_ve_so_os_proprios_eventos_e_a_ti_ve_todos(
    client, make_user, session: AsyncSession, enabled
) -> None:
    ana = await make_user(email="ana@h2d.local")
    bia = await make_user(email="bia@h2d.local")
    conversa_ana, conversa_bia = uuid.uuid4(), uuid.uuid4()
    await add_event(session, user_id=ana.id, conversation_id=conversa_ana, summary="da Ana")
    await add_event(session, user_id=bia.id, conversation_id=conversa_bia, summary="da Bia")

    client.cookies.clear()
    login = await client.post(
        "/api/auth/login", json={"email": "ana@h2d.local", "password": PASSWORD}
    )
    assert login.status_code == 200

    own = (await client.get("/api/escritorio/eventos")).json()
    assert [e["summary"] for e in own] == ["da Ana"]
    # Pedir a conversa de outra pessoa não vaza nada: volta vazio.
    other = (
        await client.get("/api/escritorio/eventos", params={"conversation_id": str(conversa_bia)})
    ).json()
    assert other == []
    assert [
        a["conversation_id"] for a in (await client.get("/api/escritorio/atendimentos")).json()
    ] == [str(conversa_ana)]

    for role in (Role.TECH, Role.ADMIN):
        await login_as(client, make_user, role, f"{role.value}@h2d.local")
        everything = (await client.get("/api/escritorio/eventos")).json()
        assert {e["summary"] for e in everything} == {"da Ana", "da Bia"}
        assert len((await client.get("/api/escritorio/atendimentos")).json()) == 2


async def test_replay_de_um_chamado_traz_a_conversa_antes_dele_em_ordem(
    client, make_user, session: AsyncSession, enabled
) -> None:
    owner = await make_user(email="ana@h2d.local")
    conversation, ticket = uuid.uuid4(), uuid.uuid4()
    base = datetime.now(UTC) - timedelta(minutes=2)
    await add_event(
        session,
        room="rag",
        action="rag_busca",
        user_id=owner.id,
        conversation_id=conversation,
        at=base + timedelta(seconds=2),
        summary="segundo",
    )
    await add_event(
        session, user_id=owner.id, conversation_id=conversation, at=base, summary="primeiro"
    )
    await add_event(
        session,
        room="tecnicos",
        action="chamado_criado",
        user_id=owner.id,
        conversation_id=conversation,
        ticket_id=ticket,
        at=base + timedelta(seconds=4),
        summary="terceiro",
        metadata={"codigo": "H2D-0042"},
    )
    await add_event(session, user_id=owner.id, conversation_id=uuid.uuid4(), summary="outro")
    await login_as(client, make_user, Role.TECH, "tec@h2d.local")

    replay = (await client.get("/api/escritorio/eventos", params={"ticket_id": str(ticket)})).json()
    assert [e["summary"] for e in replay] == ["primeiro", "segundo", "terceiro"]

    after = (
        await client.get(
            "/api/escritorio/eventos",
            params={"ticket_id": str(ticket), "after": replay[0]["created_at"]},
        )
    ).json()
    assert [e["summary"] for e in after] == ["segundo", "terceiro"]

    atendimento = next(
        a
        for a in (await client.get("/api/escritorio/atendimentos")).json()
        if a["conversation_id"] == str(conversation)
    )
    assert atendimento["ticket_id"] == str(ticket)
    assert atendimento["ticket_code"] == "H2D-0042"
    assert atendimento["events"] == 3


# ---------------------------------------------------------------- SSE


async def test_sse_entrega_os_eventos_na_ordem_so_do_dono(
    client, make_user, session: AsyncSession, enabled
) -> None:
    ana = await make_user(email="ana@h2d.local")
    bia = await make_user(email="bia@h2d.local")
    past = datetime.now(UTC) - timedelta(minutes=1)
    await add_event(session, user_id=ana.id, at=past + timedelta(seconds=1), summary="1")
    await add_event(session, user_id=bia.id, at=past + timedelta(seconds=2), summary="de outra")
    await add_event(
        session, room="triagem", user_id=ana.id, at=past + timedelta(seconds=3), summary="2"
    )
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": "ana@h2d.local", "password": PASSWORD})

    response = await client.get("/api/escritorio/stream", params={"after": past.isoformat()})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [e["summary"] for e in sse_events(response.text)] == ["1", "2"]


async def test_sse_ao_vivo_nao_repete_o_que_aconteceu_antes_de_conectar(
    client, make_user, session: AsyncSession, enabled
) -> None:
    ana = await make_user(email="ana@h2d.local")
    now = datetime.now(UTC)
    await add_event(session, user_id=ana.id, at=now - timedelta(seconds=10), summary="antigo")
    await add_event(session, user_id=ana.id, at=now + timedelta(seconds=30), summary="novo")
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": "ana@h2d.local", "password": PASSWORD})

    response = await client.get("/api/escritorio/stream")

    assert [e["summary"] for e in sse_events(response.text)] == ["novo"]


async def test_sse_retoma_pelo_last_event_id_sem_repetir(
    client, make_user, session: AsyncSession, enabled
) -> None:
    ana = await make_user(email="ana@h2d.local")
    past = datetime.now(UTC) - timedelta(minutes=1)
    first = await add_event(session, user_id=ana.id, at=past, summary="1")
    await add_event(session, user_id=ana.id, at=past + timedelta(seconds=1), summary="2")
    await add_event(session, user_id=ana.id, at=past + timedelta(seconds=2), summary="3")
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": "ana@h2d.local", "password": PASSWORD})

    response = await client.get("/api/escritorio/stream", headers={"Last-Event-ID": str(first.id)})

    assert [e["summary"] for e in sse_events(response.text)] == ["2", "3"]


async def test_sse_filtra_por_chamado_e_ignora_last_event_id_de_outra_pessoa(
    client, make_user, session: AsyncSession, enabled
) -> None:
    ana = await make_user(email="ana@h2d.local")
    bia = await make_user(email="bia@h2d.local")
    ticket = uuid.uuid4()
    past = datetime.now(UTC) - timedelta(minutes=1)
    await add_event(session, user_id=ana.id, ticket_id=ticket, at=past, summary="do chamado")
    await add_event(session, user_id=ana.id, at=past, summary="de outro atendimento")
    alheio = await add_event(session, user_id=bia.id, at=past + timedelta(seconds=5), summary="Bia")
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": "ana@h2d.local", "password": PASSWORD})

    response = await client.get(
        "/api/escritorio/stream",
        params={"ticket_id": str(ticket), "after": (past - timedelta(seconds=1)).isoformat()},
        headers={"Last-Event-ID": str(alheio.id)},  # não é dela: o cursor não pode ser usado
    )

    assert [e["summary"] for e in sse_events(response.text)] == ["do chamado"]


# ---------------------------------------------------------------- webhook do n8n


async def test_webhook_assinado_grava_o_evento_ja_sanitizado(
    client, session: AsyncSession, enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "n8n_hmac_secret", SecretStr(SEGREDO))
    owner, conversation = uuid.uuid4(), uuid.uuid4()
    raw, headers = signed(
        SEGREDO,
        {
            "room": "tecnicos",
            "action": "aviso_enviado",
            "summary": "E-mail enviado. senha: Abc12345",
            "agent_name": "n8n",
            "user_id": str(owner),
            "conversation_id": str(conversation),
            "metadata": {"canal": "email", "password": "x"},
        },
    )

    response = await client.post("/api/hooks/n8n/escritorio/events", content=raw, headers=headers)

    assert response.status_code == 201
    saved = await session.scalar(select(AgentEvent).where(AgentEvent.action == "aviso_enviado"))
    assert saved is not None
    assert saved.agent_name == "n8n"
    assert saved.user_id == owner and saved.conversation_id == conversation
    assert "Abc12345" not in saved.summary
    assert saved.event_metadata == {"canal": "email"}


async def test_webhook_barra_assinatura_ruim_sala_invalida_e_integracao_desligada(
    client, enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = {"room": "rag", "action": "rag_busca", "summary": "busca"}
    raw, headers = signed(SEGREDO, body)

    # Sem segredo configurado a integração fica desligada.
    off = await client.post("/api/hooks/n8n/escritorio/events", content=raw, headers=headers)
    assert off.status_code == 503

    monkeypatch.setattr(get_settings(), "n8n_hmac_secret", SecretStr(SEGREDO))
    wrong = {**headers, "X-H2D-Signature": "sha256=abc"}
    assert (
        await client.post("/api/hooks/n8n/escritorio/events", content=raw, headers=wrong)
    ).status_code == 401

    bad_room, bad_headers = signed(SEGREDO, {**body, "room": "cozinha"})
    assert (
        await client.post("/api/hooks/n8n/escritorio/events", content=bad_room, headers=bad_headers)
    ).status_code == 422
