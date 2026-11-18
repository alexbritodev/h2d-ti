"""Testes de ponta a ponta do pipeline com Agente 1 (Guardião) e Agente 2 (Validador)."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.agents import (
    GUARDIAO_BLOCKED_MESSAGE,
    NOT_FOUND_MANUALS_MESSAGE,
)
from h2d.chat.service import handle_user_message
from h2d.kb.embeddings import FakeEmbedder
from h2d.kb.search import Hit
from h2d.llm.client import FakeLLM
from h2d.models import Conversation, LlmCall, PromptVersion, Role, User


def _mock_user_and_conv() -> tuple[User, Conversation]:
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    user = User(
        id=user_id,
        name="Colaborador Teste",
        email="teste@h2d.local",
        password_hash="fakehash",
        role=Role.USER,
        is_active=True,
    )
    conv = Conversation(id=conv_id, user_id=user_id)
    return user, conv


@pytest.mark.asyncio
async def test_pipeline_guardiao_blocks_bad_content() -> None:
    """Se o Guardião reprovar, nem o RAG nem a LLM de resposta podem ser chamados."""
    user, conv = _mock_user_and_conv()
    events: list[dict[str, Any]] = []

    async def on_progress(ev: dict[str, Any]) -> None:
        events.append(ev)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.scalar.return_value = 0
    mock_session.scalars.return_value = []

    fake_llm = FakeLLM()
    fake_embedder = FakeEmbedder()

    with patch("h2d.chat.service.search_chunks") as mock_search:
        result = await handle_user_message(
            mock_session,
            user=user,
            conversation=conv,
            text="Que porra de sistema que não funciona!",
            llm=fake_llm,
            embedder=fake_embedder,
            on_progress=on_progress,
        )

        # 1. RAG search nunca foi chamado
        mock_search.assert_not_called()
        # 2. LLM nunca foi chamada
        assert len(fake_llm.calls) == 0
        # 3. Resposta devolve a mensagem educada do Guardião
        assert GUARDIAO_BLOCKED_MESSAGE in result.message.content
        assert result.reason == "guardiao_blocked"
        # 4. Eventos emitidos registram reprovação do guardião
        guardiao_events = [e for e in events if e["agente"] == "guardiao"]
        assert any(e["status"] == "reprovado" for e in guardiao_events)


@pytest.mark.asyncio
async def test_pipeline_empty_rag_skips_generation() -> None:
    """Se a busca RAG não trouxer nada, pula geração da resposta e avisa o usuário."""
    user, conv = _mock_user_and_conv()
    events: list[dict[str, Any]] = []

    async def on_progress(ev: dict[str, Any]) -> None:
        events.append(ev)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.scalar.return_value = 0
    mock_session.scalars.return_value = []

    class ProductionLLM:
        model_name = "production-model"

        def __init__(self) -> None:
            self.calls: list[Any] = []

        async def complete(self, messages: Any, **kwargs: Any) -> Any:
            self.calls.append(messages)
            return await FakeLLM().complete(messages, **kwargs)

    llm = ProductionLLM()
    fake_embedder = FakeEmbedder()

    dummy_version = PromptVersion(name="chat_system", version=1, content="prompt", is_active=True)
    with (
        patch("h2d.chat.service.get_prompt_version", return_value=dummy_version),
        patch("h2d.chat.service.search_chunks", return_value=[]),
        patch("h2d.chat.service.expand_sections", return_value=[]),
    ):
        result = await handle_user_message(
            mock_session,
            user=user,
            conversation=conv,
            text="Como configuro o software inexistente XPTO?",
            llm=llm,
            embedder=fake_embedder,
            on_progress=on_progress,
        )

        # LLM nunca deve ser chamada para responder com fontes
        sources_calls = [c for c in llm.calls if any("<fontes>" in m.content for m in c)]
        assert len(sources_calls) == 0
        # Mensagem avisa que não consta nos manuais
        assert (
            NOT_FOUND_MANUALS_MESSAGE in result.message.content
            or "não encontrei" in result.message.content.lower()
            or result.action in ("not_found", "clarify")
        )
        # Evento RAG registra reprovado
        rag_events = [e for e in events if e["agente"] == "rag"]
        assert any(e["status"] == "reprovado" for e in rag_events)


@pytest.mark.asyncio
async def test_pipeline_full_flow_with_validator_approval() -> None:
    """Fluxo normal: Guardião aprova, RAG acha manuais, LLM responde, Validador valida."""
    user, conv = _mock_user_and_conv()
    events: list[dict[str, Any]] = []

    async def on_progress(ev: dict[str, Any]) -> None:
        events.append(ev)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.scalar.return_value = 0
    mock_session.scalars.return_value = []

    hit = Hit(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Manual VPN",
        breadcrumb="Redes > VPN",
        content="A sessão da VPN dura 12 horas.",
        visibility="public",
        score=0.9,
        kind="kb",
    )

    def llm_handler(messages) -> str:
        if "Critérios:" in messages[0].content or "Validador" in messages[0].content:
            # Resposta do Validador
            return """{
                "valida": true,
                "confianca": 0.95,
                "afirmacoes_sem_respaldo": [],
                "motivo": "Totalmente fundamentada no manual da VPN [1]."
            }"""
        # Resposta da geração
        return "A sessão da VPN dura 12 horas conforme o procedimento [1]."

    fake_llm = FakeLLM(llm_handler)
    fake_embedder = FakeEmbedder()
    dummy_version = PromptVersion(name="chat_system", version=1, content="prompt", is_active=True)

    with (
        patch("h2d.chat.service.get_prompt_version", return_value=dummy_version),
        patch("h2d.chat.service.search_chunks", return_value=[hit]),
        patch("h2d.chat.service.expand_sections", return_value=[hit]),
    ):
        result = await handle_user_message(
            mock_session,
            user=user,
            conversation=conv,
            text="Qual a duração da sessão da VPN corporativa?",
            llm=fake_llm,
            embedder=fake_embedder,
            on_progress=on_progress,
        )

        assert result.action == "answered"
        assert "12 horas" in result.message.content
        assert len(result.citations) > 0

        # Verifica a sequência completa de eventos dos agentes
        agent_names = [e["agente"] for e in events]
        assert "guardiao" in agent_names
        assert "rag" in agent_names
        assert "llm" in agent_names
        assert "validador" in agent_names

        validador_events = [e for e in events if e["agente"] == "validador"]
        assert any(e["status"] == "aprovado" for e in validador_events)


@pytest.mark.asyncio
async def test_pipeline_critical_triage_closes_all_stages() -> None:
    """Triagem crítica deve concluir os 4 estágios da timeline sem deixar etapas aguardando."""
    user, conv = _mock_user_and_conv()
    events: list[dict[str, Any]] = []

    async def on_progress(ev: dict[str, Any]) -> None:
        events.append(ev)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.scalar.return_value = 0
    mock_session.scalars.return_value = []

    fake_llm = FakeLLM(lambda _messages: "Encaminhando imediatamente para a equipe de TI.")
    fake_embedder = FakeEmbedder()

    result = await handle_user_message(
        mock_session,
        user=user,
        conversation=conv,
        text="Acho que sofri um ransomware no computador!",
        llm=fake_llm,
        embedder=fake_embedder,
        on_progress=on_progress,
    )

    assert result.action == "escalate"
    latest = {e["agente"]: e["status"] for e in events}
    assert latest == {
        "guardiao": "aprovado",
        "rag": "aprovado",
        "llm": "aprovado",
        "validador": "aprovado",
    }


@pytest.mark.asyncio
async def test_pipeline_greeting_with_empty_rag_reaches_smalltalk_and_logs_guardiao() -> None:
    """Saudações com RAG vazio não caem no erro de manual ausente e registram LlmCall."""
    user, conv = _mock_user_and_conv()
    events: list[dict[str, Any]] = []

    async def on_progress(ev: dict[str, Any]) -> None:
        events.append(ev)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.scalar.return_value = 0
    mock_session.scalars.return_value = []

    class ProductionLLM:
        model_name = "production-model"

        async def complete(self, messages: Any, **kwargs: Any) -> Any:
            sys_prompt = messages[0].content
            if "Guardião" in sys_prompt:
                return await FakeLLM(
                    lambda _m: '{"aprovado": true, "categoria": "ok", "motivo": "Saudação"}'
                ).complete(messages, **kwargs)
            return await FakeLLM(
                lambda _m: "[CONVERSA] Olá! Como posso ajudar você hoje na TI?"
            ).complete(messages, **kwargs)

    llm = ProductionLLM()
    fake_embedder = FakeEmbedder()
    dummy_version = PromptVersion(name="chat_system", version=1, content="prompt", is_active=True)

    with (
        patch("h2d.chat.service.get_prompt_version", return_value=dummy_version),
        patch("h2d.chat.service.search_chunks", return_value=[]),
        patch("h2d.chat.service.expand_sections", return_value=[]),
    ):
        result = await handle_user_message(
            mock_session,
            user=user,
            conversation=conv,
            text="Olá, tudo bem?",
            llm=llm,
            embedder=fake_embedder,
            on_progress=on_progress,
        )

    assert result.action == "smalltalk"
    assert "Olá! Como posso ajudar" in result.message.content
    latest = {e["agente"]: e["status"] for e in events}
    assert latest == {
        "guardiao": "aprovado",
        "rag": "aprovado",
        "llm": "aprovado",
        "validador": "aprovado",
    }
    added_calls = [
        call.args[0]
        for call in mock_session.add.call_args_list
        if isinstance(call.args[0], LlmCall)
    ]
    assert [c.purpose for c in added_calls] == ["guardiao", "answer"]
