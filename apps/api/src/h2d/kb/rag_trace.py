"""Rastreio do RAG para o painel do administrador: mostra cada etapa da busca com dados reais.

Tudo aqui só lê. Não chama o modelo de linguagem (sem custo e sem gastar o teto diário) e não grava
nada. As consultas repetem as da busca de verdade (`kb.search`), com colunas a mais para expor
posições, distâncias e pontuações; um teste confere que os trechos escolhidos são os mesmos.
"""

import asyncio
import re
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.chat import prompts
from h2d.chat.masking import mask_sensitive
from h2d.chat.service import (
    ANSWER_MAX_TOKENS,
    HISTORY_MESSAGES,
    SEARCH_LIMIT,
    _sources_block,
    llm_calls_today,
)
from h2d.config import get_settings
from h2d.kb.embeddings import Embedder, embed_async
from h2d.kb.search import CANDIDATES, RRF_K, Hit, _tsquery
from h2d.kb.text import DEFAULT_MAX_WORDS
from h2d.models import EMBEDDING_DIM

# Janela de leitura do MiniLM (ADR-003): o que passa disso não entra no vetor do trecho.
MODEL_MAX_TOKENS = 128
SHOWN = 8
FUSION_SHOWN = 12
SNIPPET_CHARS = 240
EMBEDDING_ROUND = 4


class TokenOut(BaseModel):
    text: str
    id: int


class WordOut(BaseModel):
    """Uma palavra da pergunta e o que o Postgres faz com ela (radical ou descarte)."""

    word: str
    lexeme: str | None  # None: é palavra vazia (artigo, preposição...) e sai da busca por palavras


class MaskingStage(BaseModel):
    original_chars: int
    masked_text: str
    redactions: int
    kinds: list[str]


class TokenizationStage(BaseModel):
    model_tokens: list[TokenOut]
    model_token_count: int
    model_max_tokens: int
    words: list[WordOut]
    tsquery_raw: str
    tsquery_parsed: str


class EmbeddingStage(BaseModel):
    model: str
    dimensions: int
    norm: float
    minimum: float
    maximum: float
    values: list[float]


class VectorHit(BaseModel):
    chunk_id: UUID
    title: str
    breadcrumb: str
    snippet: str
    rank: int
    similarity: float


class LexicalHit(BaseModel):
    chunk_id: UUID
    title: str
    breadcrumb: str
    snippet: str
    rank: int
    score: float


class FusionRow(BaseModel):
    chunk_id: UUID
    title: str
    breadcrumb: str
    snippet: str
    vector_rank: int | None
    lexical_rank: int | None
    vector_part: float
    lexical_part: float
    score: float
    selected: bool


class SelectedChunk(BaseModel):
    chunk_id: UUID
    title: str
    breadcrumb: str
    position: int
    token_count: int
    truncated: bool


class PromptStage(BaseModel):
    system_prompt: str
    sources_block: str
    question: str
    history_messages: int
    sources: list[SelectedChunk]
    approx_input_tokens: int


class GenerationStage(BaseModel):
    model: str
    fallbacks: list[str]
    temperature: float
    max_tokens: int
    calls_per_turn: str
    daily_limit: int
    calls_today: int


class Timing(BaseModel):
    stage: str
    label: str
    ms: float


class TraceOut(BaseModel):
    question: str
    masking: MaskingStage
    tokenization: TokenizationStage
    embedding: EmbeddingStage
    vector: list[VectorHit]
    lexical: list[LexicalHit]
    fusion: list[FusionRow]
    rrf_k: int
    candidates: int
    search_limit: int
    prompt: PromptStage
    generation: GenerationStage
    timings: list[Timing]
    total_ms: float


_TRACE_SQL = text(
    """
WITH vec AS (
  SELECT c.id, c.embedding <=> CAST(:qv AS vector) AS dist,
         row_number() OVER (ORDER BY c.embedding <=> CAST(:qv AS vector)) AS rank
  FROM kb_chunks c JOIN kb_document_versions v ON v.id = c.version_id
  WHERE v.status = 'active' AND (CAST(:can_it AS boolean) OR c.visibility = 'public')
  ORDER BY c.embedding <=> CAST(:qv AS vector)
  LIMIT :n
), lex AS (
  SELECT c.id, ts_rank_cd(c.tsv, q.query) AS score,
         row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q.query) DESC) AS rank
  FROM kb_chunks c
  JOIN kb_document_versions v ON v.id = c.version_id,
       (SELECT to_tsquery('portuguese', :tsq) AS query) q
  WHERE v.status = 'active' AND c.tsv @@ q.query
    AND (CAST(:can_it AS boolean) OR c.visibility = 'public')
  ORDER BY ts_rank_cd(c.tsv, q.query) DESC
  LIMIT :n
)
SELECT c.id, c.document_id, d.title, c.breadcrumb, c.content, c.visibility, c."position",
       vec.rank AS vec_rank, vec.dist, lex.rank AS lex_rank, lex.score AS lex_score,
       COALESCE(1.0 / (CAST(:k AS integer) + vec.rank), 0) AS vec_part,
       COALESCE(1.0 / (CAST(:k AS integer) + lex.rank), 0) AS lex_part
FROM vec FULL OUTER JOIN lex ON vec.id = lex.id
JOIN kb_chunks c ON c.id = COALESCE(vec.id, lex.id)
JOIN kb_documents d ON d.id = c.document_id
"""
)

_WORDS_SQL = text(
    "SELECT w AS word, to_tsvector('portuguese', w)::text AS lexeme "
    "FROM unnest(CAST(:words AS text[])) AS w"
)
_TSQUERY_SQL = text("SELECT to_tsquery('portuguese', :tsq)::text")
_TSV_ITEM = re.compile(r"'((?:[^']|'')*)'(?::([0-9A-D,]+))?")


def _snippet(content: str) -> str:
    flat = " ".join(content.split())
    return flat if len(flat) <= SNIPPET_CHARS else flat[: SNIPPET_CHARS - 1].rstrip() + "…"


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


async def tokenize_for_model(embedder: Embedder, content: str) -> list[TokenOut]:
    """Tokens do tokenizador do modelo. Um embedder sem tokenizador devolve lista vazia."""
    tokenize: Callable[[str], list[tuple[str, int]]] | None = getattr(embedder, "tokenize", None)
    if tokenize is None or not content.strip():
        return []
    pairs = await asyncio.to_thread(tokenize, content)
    return [TokenOut(text=token, id=token_id) for token, token_id in pairs]


def parse_tsvector(value: str) -> list[tuple[str, int]]:
    """`'conect':1,4 'vpn':2` vira [("conect", 2), ("vpn", 1)], do mais ao menos frequente."""
    items = [
        (match.group(1).replace("''", "'"), len((match.group(2) or "").split(",")))
        for match in _TSV_ITEM.finditer(value)
    ]
    return sorted(items, key=lambda item: (-item[1], item[0]))


def parse_vector(value: str) -> list[float]:
    return [float(x) for x in value.strip("[]").split(",") if x]


async def _words(session: AsyncSession, question: str) -> list[WordOut]:
    words = list(dict.fromkeys(re.findall(r"[^\W_]{2,}", question.lower())))
    if not words:
        return []
    rows = await session.execute(_WORDS_SQL, {"words": words})
    by_word = {r.word: r.lexeme for r in rows}
    out = []
    for word in words:
        parsed = parse_tsvector(by_word.get(word, ""))
        out.append(WordOut(word=word, lexeme=parsed[0][0] if parsed else None))
    return out


def _hit_from_row(row: Any) -> Hit:
    return Hit(
        row.id, row.document_id, row.title, row.breadcrumb, row.content, str(row.visibility),
        float(row.vec_part + row.lex_part),
    )  # fmt: skip


async def trace_question(
    session: AsyncSession, embedder: Embedder, question: str, *, can_see_it: bool = True
) -> TraceOut:
    clock = time.perf_counter
    timings: list[Timing] = []
    # O modelo carrega na primeira chamada (segundos). Aquecer antes de medir evita atribuir essa
    # carga única à tokenização.
    await embed_async(embedder, ["aquecimento"])

    def mark(stage: str, label: str, started: float) -> float:
        now = clock()
        timings.append(Timing(stage=stage, label=label, ms=round((now - started) * 1000, 1)))
        return now

    begin = step = clock()
    masked = mask_sensitive(question)
    masking = MaskingStage(
        original_chars=len(question),
        masked_text=masked.text,
        redactions=masked.redactions,
        kinds=sorted(masked.kinds),
    )
    step = mark("masking", "Mascaramento", step)
    query = masked.text

    model_tokens = await tokenize_for_model(embedder, query)
    words = await _words(session, query)
    tsq = _tsquery(query)
    parsed_query = (await session.scalar(_TSQUERY_SQL, {"tsq": tsq})) if tsq else ""
    tokenization = TokenizationStage(
        model_tokens=model_tokens,
        model_token_count=len(model_tokens),
        model_max_tokens=MODEL_MAX_TOKENS,
        words=words,
        tsquery_raw=tsq,
        tsquery_parsed=parsed_query or "",
    )
    step = mark("tokenization", "Tokenização", step)

    [vector] = await embed_async(embedder, [query]) if query.strip() else [[]]
    norm = sum(x * x for x in vector) ** 0.5
    embedding = EmbeddingStage(
        model=embedder.model_name,
        dimensions=len(vector),
        norm=round(norm, 4),
        minimum=round(min(vector, default=0.0), EMBEDDING_ROUND),
        maximum=round(max(vector, default=0.0), EMBEDDING_ROUND),
        values=[round(x, EMBEDDING_ROUND) for x in vector],
    )
    step = mark("embedding", "Embedding", step)

    rows: list[Any] = []
    if vector:
        # Mesmos ajustes de sessão da busca de verdade.
        await session.execute(text("SELECT '[1]'::vector"))
        await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        rows = list(
            await session.execute(
                _TRACE_SQL,
                {
                    "qv": _vector_literal(vector), "tsq": tsq, "can_it": can_see_it,
                    "n": CANDIDATES, "k": RRF_K,
                },
            )
        )  # fmt: skip
    vector_rows = sorted((r for r in rows if r.vec_rank is not None), key=lambda r: r.vec_rank)
    lexical_rows = sorted((r for r in rows if r.lex_rank is not None), key=lambda r: r.lex_rank)
    vector_hits = [
        VectorHit(
            chunk_id=r.id, title=r.title, breadcrumb=r.breadcrumb, snippet=_snippet(r.content),
            rank=int(r.vec_rank), similarity=round(1 - float(r.dist), 4),
        )
        for r in vector_rows[:SHOWN]
    ]  # fmt: skip
    lexical_hits = [
        LexicalHit(
            chunk_id=r.id, title=r.title, breadcrumb=r.breadcrumb, snippet=_snippet(r.content),
            rank=int(r.lex_rank), score=round(float(r.lex_score), 4),
        )
        for r in lexical_rows[:SHOWN]
    ]  # fmt: skip
    step = mark("search", "Busca vetorial e por palavras", step)

    ranked = sorted(
        rows,
        key=lambda r: (-(float(r.vec_part) + float(r.lex_part)), r.vec_rank or 10**6, r.id.int),
    )
    selected_ids = {r.id for r in ranked[:SEARCH_LIMIT]}
    fusion = [
        FusionRow(
            chunk_id=r.id, title=r.title, breadcrumb=r.breadcrumb, snippet=_snippet(r.content),
            vector_rank=int(r.vec_rank) if r.vec_rank is not None else None,
            lexical_rank=int(r.lex_rank) if r.lex_rank is not None else None,
            vector_part=round(float(r.vec_part), 5), lexical_part=round(float(r.lex_part), 5),
            score=round(float(r.vec_part) + float(r.lex_part), 5), selected=r.id in selected_ids,
        )
        for r in ranked[:FUSION_SHOWN]
    ]  # fmt: skip
    step = mark("fusion", "Fusão RRF", step)

    chosen = ranked[:SEARCH_LIMIT]
    sources = []
    for r in chosen:
        count = len(await tokenize_for_model(embedder, r.content))
        sources.append(
            SelectedChunk(
                chunk_id=r.id, title=r.title, breadcrumb=r.breadcrumb, position=int(r.position),
                token_count=count, truncated=count > MODEL_MAX_TOKENS,
            )
        )  # fmt: skip
    block = _sources_block([_hit_from_row(r) for r in chosen]) if chosen else ""
    user_message = f"{block}\n\nPergunta: {masked.text}" if chosen else ""
    prompt = PromptStage(
        system_prompt=prompts.ANSWER_PROMPT,
        sources_block=block,
        question=masked.text,
        history_messages=HISTORY_MESSAGES,
        sources=sources,
        # Estimativa grosseira para português: um token a cada 4 caracteres.
        approx_input_tokens=(len(prompts.ANSWER_PROMPT) + len(user_message)) // 4,
    )
    step = mark("prompt", "Montagem do prompt", step)

    settings = get_settings()
    generation = GenerationStage(
        model=settings.openrouter_model,
        fallbacks=[m.strip() for m in settings.openrouter_fallback_models.split(",") if m.strip()],
        temperature=0.2,
        max_tokens=ANSWER_MAX_TOKENS,
        calls_per_turn="1 a 3 (reescrita, resposta e conferência)",
        daily_limit=settings.llm_daily_request_limit,
        calls_today=await llm_calls_today(session),
    )
    return TraceOut(
        question=masked.text,  # nunca devolve o texto original: ele pode ter senha ou CPF
        masking=masking,
        tokenization=tokenization,
        embedding=embedding,
        vector=vector_hits,
        lexical=lexical_hits,
        fusion=fusion,
        rrf_k=RRF_K,
        candidates=CANDIDATES,
        search_limit=SEARCH_LIMIT,
        prompt=prompt,
        generation=generation,
        timings=timings,
        total_ms=round((clock() - begin) * 1000, 1),
    )


class LexemeOut(BaseModel):
    lexeme: str
    count: int


class ChunkAnatomy(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    breadcrumb: str
    position: int
    visibility: str
    content: str
    words: int
    tokens: list[TokenOut]
    token_count: int
    model_max_tokens: int
    truncated: bool
    lexemes: list[LexemeOut]
    embedding: EmbeddingStage


_CHUNK_SQL = text(
    """
SELECT c.id, c.document_id, d.title, c.breadcrumb, c.content, c.visibility, c."position",
       c.tsv::text AS tsv, c.embedding::text AS embedding
FROM kb_chunks c JOIN kb_documents d ON d.id = c.document_id
WHERE c.id = :id
"""
)


async def chunk_anatomy(
    session: AsyncSession, embedder: Embedder, chunk_id: UUID
) -> ChunkAnatomy | None:
    """O que a ingestão guardou de um trecho: texto, tokens, radicais e vetor."""
    await session.execute(text("SELECT '[1]'::vector"))
    row = (await session.execute(_CHUNK_SQL, {"id": chunk_id})).first()
    if row is None:
        return None
    tokens = await tokenize_for_model(embedder, row.content)
    vector = parse_vector(row.embedding)
    return ChunkAnatomy(
        chunk_id=row.id,
        document_id=row.document_id,
        title=row.title,
        breadcrumb=row.breadcrumb,
        position=int(row.position),
        visibility=str(row.visibility),
        content=row.content,
        words=len(row.content.split()),
        tokens=tokens,
        token_count=len(tokens),
        model_max_tokens=MODEL_MAX_TOKENS,
        truncated=len(tokens) > MODEL_MAX_TOKENS,
        lexemes=[LexemeOut(lexeme=w, count=n) for w, n in parse_tsvector(row.tsv)[:80]],
        embedding=EmbeddingStage(
            model=embedder.model_name,
            dimensions=len(vector),
            norm=round(sum(x * x for x in vector) ** 0.5, 4),
            minimum=round(min(vector, default=0.0), EMBEDDING_ROUND),
            maximum=round(max(vector, default=0.0), EMBEDDING_ROUND),
            values=[round(x, EMBEDDING_ROUND) for x in vector],
        ),
    )


class PipelineParams(BaseModel):
    chunk_max_words: int
    model_max_tokens: int
    embedding_model: str
    embedding_dimensions: int
    rrf_k: int
    candidates: int
    search_limit: int
    history_messages: int
    answer_model: str
    daily_limit: int
    calls_today: int


class OverviewOut(BaseModel):
    documents: int
    chunks: int
    avg_words: float
    max_words: int
    public_chunks: int
    restricted_chunks: int
    params: PipelineParams


_OVERVIEW_SQL = text(
    """
SELECT count(DISTINCT c.document_id) AS documents, count(*) AS chunks,
       COALESCE(avg(w.n), 0) AS avg_words, COALESCE(max(w.n), 0) AS max_words,
       count(*) FILTER (WHERE c.visibility = 'public') AS public_chunks
FROM kb_chunks c
JOIN kb_document_versions v ON v.id = c.version_id AND v.status = 'active',
LATERAL (SELECT cardinality(regexp_split_to_array(btrim(c.content), '\\s+')) AS n) w
"""
)


async def overview(session: AsyncSession, embedder: Embedder) -> OverviewOut:
    row = (await session.execute(_OVERVIEW_SQL)).one()
    settings = get_settings()
    return OverviewOut(
        documents=int(row.documents),
        chunks=int(row.chunks),
        avg_words=round(float(row.avg_words), 1),
        max_words=int(row.max_words),
        public_chunks=int(row.public_chunks),
        restricted_chunks=int(row.chunks) - int(row.public_chunks),
        params=PipelineParams(
            chunk_max_words=DEFAULT_MAX_WORDS,
            model_max_tokens=MODEL_MAX_TOKENS,
            embedding_model=embedder.model_name,
            embedding_dimensions=EMBEDDING_DIM,
            rrf_k=RRF_K,
            candidates=CANDIDATES,
            search_limit=SEARCH_LIMIT,
            history_messages=HISTORY_MESSAGES,
            answer_model=settings.openrouter_model,
            daily_limit=settings.llm_daily_request_limit,
            calls_today=await llm_calls_today(session),
        ),
    )
