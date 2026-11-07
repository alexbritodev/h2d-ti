"""Fase 2: os eventos saem dos pontos reais do atendimento, e só com a flag ligada."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.escritorio import events
from h2d.escritorio.models import AgentEvent
from tests.test_chat import VPN, _base, _conversation, _done, _login, _say
from tests.test_tickets import _catalog, _classification, _use_classification
from tests.test_tickets import _escalate as escalate_ticket
from tests.test_tickets import _login as login_ticket


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[AgentEvent]:
    """Guarda os eventos em memória: a sessão de teste é uma só e não pode ser disputada."""
    saved: list[AgentEvent] = []

    async def keep(event: AgentEvent) -> None:
        saved.append(event)

    monkeypatch.setattr(events, "persist_event", keep)
    return saved


def set_flag(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    monkeypatch.setattr(get_settings(), "escritorio_virtual_enabled", value)


async def test_resposta_com_fonte_emite_recepcao_rag_e_resposta(
    client, make_user, session: AsyncSession, tmp_path, captured, monkeypatch
) -> None:
    set_flag(monkeypatch, True)
    await _base(session, tmp_path, VPN)
    user = await _login(client, make_user)
    conversation_id = await _conversation(client)

    sse = await _say(client, conversation_id, "quanto tempo dura a sessão da VPN")
    await events.flush_pending()

    assert _done(sse)["action"] == "answered"
    assert [(e.room, e.action) for e in captured] == [
        ("recepcao", "mensagem_recebida"),
        ("rag", "rag_busca"),
        ("recepcao", "resposta_enviada"),
    ]
    assert all(str(e.conversation_id) == conversation_id for e in captured)
    assert all(e.user_id == user.id for e in captured)
    rag = captured[1]
    assert rag.event_metadata["top_k"] == 5
    assert rag.event_metadata["fontes"] == ["VPN corporativa"]
    # O texto digitado pelo usuário nunca vai para o resumo nem para os metadados.
    assert "VPN" not in captured[0].summary
    assert captured[0].event_metadata["caracteres"] > 0


async def test_escalonar_emite_triagem_banco_tecnicos_e_auditoria_na_ordem(
    client, make_user, session: AsyncSession, app, captured, monkeypatch
) -> None:
    set_flag(monkeypatch, True)
    catalog = await _catalog(session, make_user)
    _use_classification(app, _classification())
    user = await login_ticket(client, make_user)

    ref = await escalate_ticket(client)
    await events.flush_pending()

    from_ticket = [e for e in captured if e.ticket_id is not None]
    assert [(e.room, e.action) for e in from_ticket] == [
        ("triagem", "classificado"),
        ("banco", "sql_leitura"),
        ("tecnicos", "chamado_criado"),
        ("tecnicos", "chamado_atribuido"),
        ("auditoria", "evento_registrado"),
    ]
    assert {str(e.ticket_id) for e in from_ticket} == {ref["id"]}
    assert all(e.user_id == user.id for e in from_ticket)
    classified = from_ticket[0]
    assert classified.event_metadata["categoria"] == "VPN"
    assert classified.event_metadata["prioridade"] == "P1"
    sql = from_ticket[1]
    assert sql.event_metadata["table"] == "technicians"
    # Consulta registrada sem valores: só o nome da tabela e o formato da query.
    assert "tec@h2d.local" not in str(sql.event_metadata)
    assert catalog["tech_user"].name in from_ticket[3].summary


async def test_classificacao_ausente_vai_para_triagem_manual(
    client, make_user, session: AsyncSession, app, captured, monkeypatch
) -> None:
    set_flag(monkeypatch, True)
    await _catalog(session, make_user)
    _use_classification(app, "isto não é JSON")
    await login_ticket(client, make_user)

    await escalate_ticket(client)
    await events.flush_pending()

    actions = [e.action for e in captured if e.ticket_id is not None]
    assert actions[0] == "triagem_manual"
    assert actions[-1] == "evento_registrado"


async def test_com_a_flag_desligada_o_comportamento_e_o_mesmo_e_nada_e_emitido(
    client, make_user, session: AsyncSession, app, tmp_path, captured, monkeypatch
) -> None:
    set_flag(monkeypatch, False)
    await _base(session, tmp_path, VPN)
    await _catalog(session, make_user)
    _use_classification(app, _classification())
    await login_ticket(client, make_user)
    conversation_id = await _conversation(client)

    sse = await _say(client, conversation_id, "quanto tempo dura a sessão da VPN")
    ref = await escalate_ticket(client)
    await events.flush_pending()

    # Mesmas respostas de sempre: resposta citada em SSE e chamado classificado e atribuído.
    assert [name for name, _ in sse][0] == "status" and [name for name, _ in sse][-1] == "done"
    assert _done(sse)["action"] == "answered"
    assert ref["code"].startswith("H2D-")
    assert captured == []


async def test_falha_ao_gravar_o_evento_nao_atrapalha_o_chat(
    client, make_user, session: AsyncSession, tmp_path, monkeypatch
) -> None:
    set_flag(monkeypatch, True)

    async def broken(_: AgentEvent) -> None:
        raise RuntimeError("banco de eventos fora do ar")

    monkeypatch.setattr(events, "persist_event", broken)
    await _base(session, tmp_path, VPN)
    await _login(client, make_user)
    conversation_id = await _conversation(client)

    sse = await _say(client, conversation_id, "quanto tempo dura a sessão da VPN")
    await events.flush_pending()

    assert _done(sse)["action"] == "answered"
