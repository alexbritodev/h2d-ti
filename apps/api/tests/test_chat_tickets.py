import pytest
from sqlalchemy import select

from h2d.models import Role, Ticket, TicketStatus
from tests.test_chat import VPN, _base, _conversation, _done, _login, _say, _text


async def _tickets(session, requester_id) -> None:
    session.add_all(
        [
            Ticket(
                requester_id=requester_id,
                summary="Impressora HP do financeiro não imprime",
                description="Fila travada desde ontem.",
                status=TicketStatus.IN_PROGRESS,
            ),
            Ticket(
                requester_id=requester_id,
                summary="Acesso ao sistema de RH",
                description="Pedido de liberação.",
                status=TicketStatus.RESOLVED,
                solution="Acesso liberado pelo gestor.",
            ),
        ]
    )
    await session.flush()


def _sent_to_model(app) -> str:
    return "\n".join(m.content for call in app.state.fake_llm.calls for m in call)


async def test_admin_recebe_os_chamados_como_fontes_citaveis(
    client, make_user, session, app, tmp_path
):
    await _base(session, tmp_path, VPN)
    admin = await _login(client, make_user, role=Role.ADMIN, email="admin@h2d.local")
    await _tickets(session, admin.id)
    conversation_id = await _conversation(client)
    app.state.fake_llm._handler = lambda m: "Há um chamado de impressora em andamento [2]."

    events = await _say(client, conversation_id, "tem algum chamado sobre impressora?")

    sent = _sent_to_model(app)
    assert "Resumo dos chamados do sistema" in sent
    assert "Impressora HP do financeiro" in sent
    assert "quem pergunta é administrador" in sent
    sources = next(data for name, data in events if name == "sources")["citations"]
    assert sources and sources[0]["kind"] == "ticket"
    assert _done(events)["action"] == "answered"
    assert "impressora" in _text(events)


@pytest.mark.parametrize("role", [Role.USER, Role.TECH])
async def test_quem_nao_e_admin_nunca_recebe_chamados(
    client, make_user, session, app, tmp_path, role
):
    await _base(session, tmp_path, VPN)
    user = await _login(client, make_user, role=role, email=f"{role.value}@h2d.local")
    await _tickets(session, user.id)
    conversation_id = await _conversation(client)

    await _say(client, conversation_id, "tem algum chamado sobre impressora?")

    sent = _sent_to_model(app)
    assert "Resumo dos chamados" not in sent
    assert "Impressora HP" not in sent
    assert "administrador" not in sent.split("Pergunta:")[0].split("<fontes>")[-1]
    assert (await session.scalar(select(Ticket.id).limit(1))) is not None
