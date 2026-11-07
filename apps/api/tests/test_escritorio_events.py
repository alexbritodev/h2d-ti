import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.escritorio import events
from h2d.escritorio.models import AgentEvent


@pytest.fixture
def flag(monkeypatch: pytest.MonkeyPatch):
    """Liga ou desliga a flag só durante o teste."""

    def set_to(value: bool) -> None:
        monkeypatch.setattr(get_settings(), "escritorio_virtual_enabled", value)

    return set_to


@pytest.fixture(autouse=True)
def event_session(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    """Os eventos usam a sessão de teste, que é desfeita ao final."""

    @asynccontextmanager
    async def open_test_session():
        yield session

    monkeypatch.setattr(events, "_open_session", open_test_session)


async def all_events(session: AsyncSession) -> list[AgentEvent]:
    return list(
        await session.scalars(select(AgentEvent).order_by(AgentEvent.created_at, AgentEvent.id))
    )


async def test_com_a_flag_desligada_nada_e_gravado(flag, session: AsyncSession) -> None:
    flag(False)
    events.emit_agent_event(room="recepcao", action="mensagem_recebida", summary="oi")
    await events.flush_pending()
    assert await all_events(session) == []


async def test_evento_e_gravado_na_ordem_de_emissao(flag, session: AsyncSession) -> None:
    flag(True)
    conversation, owner = uuid.uuid4(), uuid.uuid4()
    for room, action in [("recepcao", "mensagem_recebida"), ("triagem", "classificado")]:
        events.emit_agent_event(
            room=room,
            action=action,
            summary=f"passo {action}",
            conversation_id=conversation,
            user_id=owner,
            metadata={"categoria": "Rede", "prioridade": "P3"},
        )
        # Um de cada vez: nos testes todos dividem a mesma sessão (em produção, cada um tem a sua).
        await events.flush_pending()
    saved = await all_events(session)
    assert [e.action for e in saved] == ["mensagem_recebida", "classificado"]
    assert saved[0].agent_name == "Chatbot"
    assert saved[1].user_id == owner
    assert saved[1].event_metadata == {"categoria": "Rede", "prioridade": "P3"}


async def test_falha_na_gravacao_nao_chega_ao_atendimento(
    flag, monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    flag(True)

    async def broken(_: AgentEvent) -> None:
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(events, "persist_event", broken)
    events.emit_agent_event(room="rag", action="rag_busca", summary="busca")  # não lança
    await events.flush_pending()  # a tarefa de fundo também engole o erro
    assert await all_events(session) == []


def test_sem_loop_de_eventos_a_chamada_e_ignorada(flag) -> None:
    flag(True)
    events.emit_agent_event(room="rag", action="rag_busca", summary="busca")  # não lança


async def test_sala_invalida_e_ignorada_em_silencio(flag, session: AsyncSession) -> None:
    flag(True)
    events.emit_agent_event(room="cozinha", action="cafe", summary="x")
    await events.flush_pending()
    assert await all_events(session) == []


def test_summary_nao_guarda_dados_sensiveis() -> None:
    text = "senha: Abc12345 e token sk-abcdefghijklmnopqrstuvwxyz e CPF 529.982.247-25"
    clean = events.sanitize_text(text)
    assert "Abc12345" not in clean
    assert "sk-abcdefghijklmnop" not in clean
    assert "529.982.247-25" not in clean


def test_summary_e_achatado_e_cortado() -> None:
    clean = events.sanitize_text("linha 1\nlinha 2 " + "x" * 500)
    assert "\n" not in clean
    assert len(clean) <= events.SUMMARY_MAX
    assert clean.endswith("…")


def test_metadata_descarta_chaves_sensiveis_e_tipos_estranhos() -> None:
    clean = events.sanitize_metadata(
        {
            "tabela": "technicians",
            "password": "x",
            "api_key": "y",
            "Authorization": "Bearer z",
            "cpf": "52998224725",
            "objeto": object(),
            "aninhado": {"token": "t", "ok": 1},
            "fontes": ["a", "b"],
        }
    )
    assert clean["tabela"] == "technicians"
    assert clean["aninhado"] == {"ok": 1}
    assert clean["fontes"] == ["a", "b"]
    assert clean["objeto"] is None
    for key in ("password", "api_key", "Authorization", "cpf"):
        assert key not in clean


def test_metadata_enorme_e_descartada() -> None:
    assert events.sanitize_metadata({"lista": ["x" * 150] * 20, "b": ["x" * 150] * 20}) == {
        "truncated": True
    }


def test_consulta_sql_guarda_so_tabela_e_query_parametrizada() -> None:
    meta = events.sql_metadata("technicians", "SELECT *\n  FROM technicians WHERE id = :id")
    assert meta == {"table": "technicians", "query": "SELECT * FROM technicians WHERE id = :id"}
