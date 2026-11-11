"""Fluxo do chat: mascarar, checar limites, buscar, responder com fontes e conferir a fidelidade.

Cada passo que pode falhar tem um caminho de saída que não inventa resposta: sem trecho, sem
citação, sem fidelidade ou sem modelo, o assistente diz que não achou e oferece abrir chamado.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.chat import prompts
from h2d.chat.masking import mask_sensitive
from h2d.chat.tickets_context import admin_ticket_sources
from h2d.config import get_settings
from h2d.escritorio.events import emit_agent_event
from h2d.kb.embeddings import Embedder
from h2d.kb.search import Hit, search_chunks
from h2d.llm.client import LLM, ChatMessage, LLMError, LLMResult
from h2d.models import (
    Conversation,
    ConversationStatus,
    LlmCall,
    Message,
    MessageRole,
    PromptVersion,
    Role,
    User,
)

Action = Literal[
    "answered", "clarify", "not_found", "escalate", "unavailable", "limit", "smalltalk"
]
HISTORY_MESSAGES = 6
ANSWER_MAX_TOKENS = 1500  # modelos que "pensam" gastam o limite no raciocínio e cortam a resposta
SEARCH_LIMIT = 8  # trechos têm ~60 palavras: 5 deixavam o modelo sem contexto para perguntas amplas

log = logging.getLogger("h2d.chat")


def _fidelity_failed(verdict: str) -> bool:
    """Só um NAO explícito reprova. Texto que apenas começa com N ("Nenhuma...", "Nesse caso...")
    de um modelo que explica em vez de obedecer não pode derrubar uma resposta boa."""
    return re.match(r"\W*N[AÃ]O\b", verdict.strip().upper()) is not None


class ChatLimitError(Exception):
    """Limite de uso da conversa. A mensagem é própria para aparecer ao usuário."""


@dataclass
class TurnResult:
    action: Action
    message: Message
    citations: list[dict[str, Any]] = field(default_factory=list)
    reason: str | None = None
    # Etapas do fluxo do RAG neste turno ({"id", "status", "detail"}): só o administrador as vê.
    flow: list[dict[str, str]] = field(default_factory=list)


async def get_prompt_version(session: AsyncSession) -> PromptVersion:
    """Versão ativa do prompt de resposta. Se o texto mudou no código, cria a versão seguinte."""
    current = await session.scalar(
        select(PromptVersion).where(
            PromptVersion.name == prompts.ANSWER_PROMPT_NAME, PromptVersion.is_active
        )
    )
    if current is not None and current.content == prompts.ANSWER_PROMPT:
        return current
    last = await session.scalar(
        select(func.max(PromptVersion.version)).where(
            PromptVersion.name == prompts.ANSWER_PROMPT_NAME
        )
    )
    if current is not None:
        current.is_active = False
        await session.flush()
    version = PromptVersion(
        name=prompts.ANSWER_PROMPT_NAME,
        version=(last or 0) + 1,
        content=prompts.ANSWER_PROMPT,
        is_active=True,
    )
    session.add(version)
    await session.flush()
    return version


async def llm_calls_today(session: AsyncSession) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        await session.scalar(
            select(func.count()).select_from(LlmCall).where(LlmCall.created_at >= start)
        )
    ) or 0


async def call_llm(
    session: AsyncSession,
    llm: LLM,
    purpose: str,
    messages: list[ChatMessage],
    *,
    user: User,
    conversation: Conversation,
    prompt_version: PromptVersion | None = None,
    temperature: float = 0.2,
    max_tokens: int = ANSWER_MAX_TOKENS,
) -> LLMResult:
    """Chama o modelo e grava a linha em llm_calls, com sucesso ou erro."""
    base = {
        "purpose": purpose,
        "user_id": user.id,
        "conversation_id": conversation.id,
        "prompt_version_id": prompt_version.id if prompt_version else None,
    }
    try:
        result = await llm.complete(messages, temperature=temperature, max_tokens=max_tokens)
    except LLMError as error:
        session.add(
            LlmCall(
                **base,
                model=llm.model_name,
                status="rate_limited" if error.rate_limited else "error",
                error=str(error)[:1000],
            )
        )
        await session.flush()
        raise
    session.add(
        LlmCall(
            **base,
            model=result.model,
            status="ok",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
        )
    )
    await session.flush()
    return result


def _sources_block(hits: list[Hit]) -> str:
    """Trechos num bloco delimitado. Marcas de fechamento dentro do texto são neutralizadas."""
    parts = []
    for index, hit in enumerate(hits, start=1):
        safe = re.sub(r"</?\s*fonte[^>]*>", "", hit.content, flags=re.IGNORECASE)
        parts.append(f'<fonte id="{index}" titulo="{hit.document_title}">\n{safe}\n</fonte>')
    return "<fontes>\n" + "\n".join(parts) + "\n</fontes>"


def _history(messages: list[Message]) -> list[ChatMessage]:
    recent = messages[-HISTORY_MESSAGES:]
    return [ChatMessage(m.role.value, m.content) for m in recent]


def _cited(answer: str, hits: list[Hit]) -> list[dict[str, Any]]:
    seen: list[int] = []
    for number in re.findall(r"\[(\d+)\]", answer):
        index = int(number)
        if 1 <= index <= len(hits) and index not in seen:
            seen.append(index)
    return [
        {
            "chunk_id": str(hits[i - 1].chunk_id),
            "document_id": str(hits[i - 1].document_id),
            "title": hits[i - 1].document_title,
            "breadcrumb": hits[i - 1].breadcrumb,
            "kind": hits[i - 1].kind,
        }
        for i in seen
    ]


def _matches(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def can_see_it(user: User) -> bool:
    return user.role in (Role.TECH, Role.ADMIN)


async def handle_user_message(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    text: str,
    llm: LLM,
    embedder: Embedder,
) -> TurnResult:
    settings = get_settings()
    if len(text) > settings.chat_max_message_chars:
        raise ChatLimitError(f"A mensagem passa de {settings.chat_max_message_chars} caracteres.")
    sent = (
        await session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation.id, Message.role == MessageRole.USER)
        )
    ) or 0
    if sent >= settings.chat_max_user_messages:
        raise ChatLimitError(
            "Esta conversa chegou ao limite de mensagens. Abra um chamado ou comece outra conversa."
        )

    # Tudo o que vem do usuário passa pelo mascaramento antes de qualquer gravação ou envio.
    masked = mask_sensitive(text)
    flow: list[dict[str, str]] = []

    def step(stage: str, status: str, detail: str = "") -> None:
        flow.append({"id": stage, "status": status, "detail": detail})

    step(
        "masking",
        "warn" if masked.redactions else "ok",
        f"{masked.redactions} dado(s) sensível(is) escondido(s)" if masked.redactions else "",
    )
    previous = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    )
    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=masked.text,
        redactions=masked.redactions,
        # Horário exato: o now() do banco é igual na transação inteira e embaralharia a ordem.
        created_at=datetime.now(UTC),
    )
    session.add(user_message)
    if conversation.title is None:
        conversation.title = masked.text.strip().replace("\n", " ")[:80]
    await session.flush()
    # Escritório virtual: o resumo não leva o texto do usuário, só o tamanho.
    emit_agent_event(
        room="recepcao",
        action="mensagem_recebida",
        summary="Mensagem recebida do usuário",
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        metadata={"caracteres": len(masked.text), "redacoes": masked.redactions},
    )
    note = (
        prompts.REDACTION_NOTE.format(kinds=", ".join(sorted(masked.kinds)))
        if masked.redactions
        else ""
    )

    async def reply(
        action: Action,
        body: str,
        *,
        citations: list[dict[str, Any]] | None = None,
        prompt_version: PromptVersion | None = None,
        reason: str | None = None,
    ) -> TurnResult:
        content = f"{note}\n\n{body}" if note else body
        if action in ("not_found", "clarify"):
            # Sem isto não há como saber se faltou trecho, o modelo desistiu ou a conferência vetou.
            log.warning(
                "chat sem resposta (%s): motivo=%s conversa=%s", action, reason, conversation.id
            )
        message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            action=action,
            content=content,
            citations=citations or [],
            prompt_version_id=prompt_version.id if prompt_version else None,
            created_at=datetime.now(UTC),
        )
        session.add(message)
        if action == "escalate":
            conversation.status = ConversationStatus.ESCALATED
        await session.flush()
        outcome = {"answered": "ok", "smalltalk": "ok", "clarify": "warn", "escalate": "warn"}
        step("outcome", outcome.get(action, "fail"), reason or "")
        return TurnResult(action, message, citations or [], reason, flow)

    async def compose(
        situation: str,
        fallback: str,
        reason: str,
        action: Action,
        *,
        prompt_version: PromptVersion | None = None,
    ) -> TurnResult:
        """O modelo escreve a resposta. O texto fixo só entra se ele não puder ser chamado."""
        try:
            written = await call_llm(
                session,
                llm,
                "compose",
                [
                    ChatMessage("system", prompts.COMPOSE_PROMPT.format(situation=situation)),
                    *_history(previous),
                    ChatMessage("user", masked.text),
                ],
                user=user,
                conversation=conversation,
                prompt_version=prompt_version,
                temperature=0.5,
                max_tokens=500,
            )
            body = written.text.strip()
            if not body:
                log.warning("modelo devolveu texto vazio ao compor (%s)", reason)
                body = fallback
        except LLMError:
            body = fallback
        return await reply(action, body, prompt_version=prompt_version, reason=reason)

    # Tema crítico ou pedido de humano: não tenta resolver.
    if _matches(masked.text, prompts.CRITICAL_KEYWORDS):
        step("triage", "warn", "tema crítico: vai direto para a TI")
        return await compose(
            prompts.SITUATION_CRITICAL, prompts.CRITICAL_TEXT, "critical", "escalate"
        )
    if _matches(masked.text, prompts.HUMAN_KEYWORDS):
        step("triage", "warn", "pediu a equipe de TI")
        return await compose(
            prompts.SITUATION_HUMAN, prompts.HUMAN_TEXT, "human_requested", "escalate"
        )

    step("triage", "ok", "tema comum")

    # Quanto ainda cabe no teto diário do modelo (soma de todos os usuários).
    if await llm_calls_today(session) + 2 > settings.llm_daily_request_limit:
        return await reply("limit", prompts.LIMIT_TEXT, reason="daily_limit")

    version = await get_prompt_version(session)

    query = masked.text
    if previous:
        try:
            rewritten = await call_llm(
                session,
                llm,
                "rewrite",
                [
                    ChatMessage("system", prompts.REWRITE_PROMPT),
                    *_history(previous),
                    ChatMessage("user", masked.text),
                ],
                user=user,
                conversation=conversation,
                temperature=0.0,
                max_tokens=300,
            )
            query = rewritten.text.strip() or masked.text
            step("rewrite", "ok", query)
        except LLMError:
            query = masked.text  # sem reescrita, a busca usa a pergunta como veio
            step("rewrite", "fail", "modelo fora: usou a pergunta como veio")
    else:
        step("rewrite", "skip", "primeira mensagem")

    hits = await search_chunks(
        session, query, embedder, can_see_it=can_see_it(user), limit=SEARCH_LIMIT
    )
    emit_agent_event(
        room="rag",
        action="rag_busca",
        summary=f"Busca na base: {len(hits)} trecho(s) encontrado(s)",
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        metadata={
            "top_k": SEARCH_LIMIT,
            "encontrados": len(hits),
            "fontes": sorted({hit.document_title for hit in hits})[:5],
        },
    )
    kb_hits = len(hits)
    admin_note = ""
    tickets_found = 0
    if user.role is Role.ADMIN:
        # Só o administrador enxerga os chamados do sistema: eles entram como fontes extras.
        ticket_hits = await admin_ticket_sources(session, query)
        tickets_found = len(ticket_hits)
        hits = [*hits, *ticket_hits]
        admin_note = f"\n\n{prompts.ADMIN_NOTE}"

    docs = list(dict.fromkeys(h.document_title for h in hits if h.kind == "kb"))
    found = f"{kb_hits} trecho(s) de {len(docs)} manual(is)"
    if docs:
        found += f": {'; '.join(docs[:3])}"
    if tickets_found:
        found += f" + {tickets_found} chamado(s)"
    step("search", "ok" if hits else "fail", found if hits else "nenhum trecho encontrado")

    # O chat existe para filtrar chamados: na primeira vez que não acha, pergunta e sugere assuntos
    # parecidos. Só na segunda falha seguida oferece o chamado.
    already_asked = bool(previous) and previous[-1].action == "clarify"

    async def missed(reason: str, body: str = "") -> TurnResult:
        if already_asked:
            if body:
                return await reply("not_found", body, prompt_version=version, reason=reason)
            return await compose(
                prompts.SITUATION_NOT_FOUND,
                prompts.NOT_FOUND_TEXT,
                reason,
                "not_found",
                prompt_version=version,
            )
        titles = list(dict.fromkeys(h.document_title for h in hits if h.kind == "kb"))[:3]
        related = "; ".join(titles) if titles else "nenhum"
        return await compose(
            prompts.SITUATION_CLARIFY.format(topics=related),
            prompts.CLARIFY_TOPICS_TEXT.format(topics=related) if titles else prompts.CLARIFY_TEXT,
            reason,
            "clarify",
            prompt_version=version,
        )

    try:
        answered = await call_llm(
            session,
            llm,
            "answer",
            [
                ChatMessage("system", prompts.ANSWER_PROMPT),
                *_history(previous),
                ChatMessage(
                    "user", f"{_sources_block(hits)}{admin_note}\n\nPergunta: {masked.text}"
                ),
            ],
            user=user,
            conversation=conversation,
            prompt_version=version,
        )
    except LLMError as error:
        reason = "rate_limited" if error.rate_limited else "llm_error"
        step("model", "fail", reason)
        return await reply(
            "unavailable", prompts.UNAVAILABLE_TEXT, prompt_version=version, reason=reason
        )

    answer = answered.text.strip()
    tag = re.match(r"\s*\[(NAO_ENCONTREI|CONVERSA)\]\s*", answer.upper().replace("Ã", "A"))
    if tag:
        # O próprio modelo escreveu a resposta de conversa ou de "não encontrei".
        body = answer[tag.end() :].strip()
        action: Action = "smalltalk" if tag.group(1) == "CONVERSA" else "not_found"
        if action == "smalltalk":
            if body:
                return await reply(action, body, prompt_version=version, reason="smalltalk")
            return await compose(
                prompts.SITUATION_NOT_FOUND,
                prompts.NOT_FOUND_TEXT,
                "smalltalk",
                "not_found",
                prompt_version=version,
            )
        step("model", "warn", "disse que não achou nos trechos")
        return await missed("model_declined", body)
    if not answer or "NAO_ENCONTREI" in answer.upper().replace(" ", "_"):
        step("model", "warn", "disse que não achou nos trechos")
        return await missed("model_declined")
    citations = _cited(answer, hits)
    if not citations:
        # Resposta sem fonte não vale: o assistente só afirma o que consegue citar.
        step("model", "warn", "respondeu sem citar fonte")
        return await missed("no_citation")
    step("model", "ok", f"respondeu citando {len(citations)} fonte(s)")

    try:
        verdict = await call_llm(
            session,
            llm,
            "fidelity",
            [
                ChatMessage("system", prompts.FIDELITY_PROMPT),
                ChatMessage("user", f"{_sources_block(hits)}\n\nRESPOSTA:\n{answer}"),
            ],
            user=user,
            conversation=conversation,
            prompt_version=version,
            temperature=0.0,
            max_tokens=5,
        )
        if _fidelity_failed(verdict.text):
            step("fidelity", "fail", "afirmou algo que os trechos não dizem")
            return await missed("unfaithful")
        step("fidelity", "ok", "toda afirmação tem apoio nos trechos")
    except LLMError:
        # sem a conferência, a resposta já citada segue; a falha fica em llm_calls
        step("fidelity", "skip", "conferência indisponível")

    return await reply("answered", answer, citations=citations, prompt_version=version)


async def register_feedback(session: AsyncSession, message: Message, value: int) -> Conversation:
    """👍/👎. Duas respostas seguidas sem ajudar escalonam a conversa."""
    conversation = await session.get_one(Conversation, message.conversation_id)
    message.feedback = value
    if value < 0:
        conversation.failed_attempts += 1
        if conversation.failed_attempts >= 2 and conversation.status is ConversationStatus.OPEN:
            conversation.status = ConversationStatus.ESCALATED
    else:
        conversation.failed_attempts = 0
    await session.flush()
    return conversation


def new_conversation(user: User) -> Conversation:
    return Conversation(id=uuid.uuid4(), user_id=user.id)
