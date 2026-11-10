"""Busca híbrida: vetor (pgvector, cosseno) e palavras (tsvector), combinados por RRF.

O filtro de visibilidade roda dentro das duas consultas, antes de ranquear. Quem não é técnico nem
administrador nunca recebe trecho restrito à TI, nem como candidato.
"""

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.kb.embeddings import Embedder, embed_async

RRF_K = 60
CANDIDATES = 50

_SQL = text(
    """
WITH vec AS (
  SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> CAST(:qv AS vector)) AS rank
  FROM kb_chunks c JOIN kb_document_versions v ON v.id = c.version_id
  WHERE v.status = 'active' AND (CAST(:can_it AS boolean) OR c.visibility = 'public')
  ORDER BY c.embedding <=> CAST(:qv AS vector)
  LIMIT :n
), lex AS (
  SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q.query) DESC) AS rank
  FROM kb_chunks c
  JOIN kb_document_versions v ON v.id = c.version_id,
       (SELECT to_tsquery('portuguese', :tsq) AS query) q
  WHERE v.status = 'active' AND c.tsv @@ q.query
    AND (CAST(:can_it AS boolean) OR c.visibility = 'public')
  ORDER BY ts_rank_cd(c.tsv, q.query) DESC
  LIMIT :n
), fused AS (
  SELECT COALESCE(vec.id, lex.id) AS id,
         COALESCE(1.0 / (CAST(:k AS integer) + vec.rank), 0)
         + COALESCE(1.0 / (CAST(:k AS integer) + lex.rank), 0) AS score
  FROM vec FULL OUTER JOIN lex ON vec.id = lex.id
)
SELECT c.id, c.document_id, d.title, c.breadcrumb, c.content, c.visibility, f.score
FROM fused f
JOIN kb_chunks c ON c.id = f.id
JOIN kb_documents d ON d.id = c.document_id
ORDER BY f.score DESC
LIMIT :limit
"""
)


@dataclass(frozen=True)
class Hit:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    breadcrumb: str
    content: str
    visibility: str
    score: float
    kind: str = "kb"  # "ticket" quando a fonte é um chamado (só no chat do administrador)


def _tsquery(query: str) -> str:
    """Palavras da pergunta ligadas por OU: pergunta em linguagem natural nunca casa tudo."""
    words = dict.fromkeys(re.findall(r"[^\W_]{2,}", query.lower()))
    return " | ".join(words)


async def search_chunks(
    session: AsyncSession,
    query: str,
    embedder: Embedder,
    *,
    can_see_it: bool,
    limit: int = 5,
) -> list[Hit]:
    if not query.strip():
        return []
    [vector] = await embed_async(embedder, [query])
    # O parâmetro do pgvector só existe depois que a biblioteca é carregada: usar o tipo antes.
    await session.execute(text("SELECT '[1]'::vector"))
    await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    rows = await session.execute(
        _SQL,
        {
            "qv": "[" + ",".join(f"{x:.6f}" for x in vector) + "]",
            "tsq": _tsquery(query),
            "can_it": can_see_it,
            "n": CANDIDATES,
            "k": RRF_K,
            "limit": limit,
        },
    )
    return [
        Hit(
            r.id, r.document_id, r.title, r.breadcrumb, r.content, str(r.visibility), float(r.score)
        )
        for r in rows
    ]
