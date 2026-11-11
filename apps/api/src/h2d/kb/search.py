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
       (SELECT to_tsquery('portuguese', h2d_unaccent(:tsq)) AS query) q
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


_SECTION_SQL = text(
    """
SELECT h.id AS hit_id, c.id AS id, c.content
FROM kb_chunks h
JOIN kb_chunks c ON c.version_id = h.version_id AND c.document_id = h.document_id
                AND c.breadcrumb = h.breadcrumb
WHERE h.id = ANY(CAST(:ids AS uuid[])) AND (CAST(:can_it AS boolean) OR c.visibility = 'public')
  AND abs(c."position" - h."position") <= :radius
ORDER BY h.id, c."position"
"""
)


async def expand_sections(
    session: AsyncSession, hits: list[Hit], *, can_see_it: bool, radius: int = 2
) -> list[Hit]:
    """Cada trecho tem ~60 palavras, e um passo a passo costuma ocupar vários. Devolve cada trecho
    achado junto dos vizinhos da mesma seção, na ordem do manual. O trecho que já entrou na
    leitura de outro não aparece duas vezes. A mesma regra de visibilidade vale para os vizinhos."""
    kb = [h for h in hits if h.kind == "kb"]
    if not kb:
        return hits
    rows = await session.execute(
        _SECTION_SQL,
        {"ids": [str(h.chunk_id) for h in kb], "can_it": can_see_it, "radius": radius},
    )
    around: dict[UUID, list[tuple[UUID, str]]] = {}
    for row in rows:
        around.setdefault(row.hit_id, []).append((row.id, row.content))
    covered: set[UUID] = set()
    expanded: dict[UUID, Hit] = {}
    for hit in kb:
        neighbours = around.get(hit.chunk_id)
        if not neighbours or hit.chunk_id in covered:
            continue
        covered.update(chunk_id for chunk_id, _ in neighbours)
        content = "\n\n".join(text_ for _, text_ in neighbours)
        expanded[hit.chunk_id] = Hit(
            hit.chunk_id,
            hit.document_id,
            hit.document_title,
            hit.breadcrumb,
            content,
            hit.visibility,
            hit.score,
        )
    # Sem vizinhos no banco (ou já cobertos), o trecho segue como veio; os de outras fontes também.
    out: list[Hit] = []
    for hit in hits:
        if hit.kind != "kb":
            out.append(hit)
        elif hit.chunk_id in expanded:
            out.append(expanded[hit.chunk_id])
        elif hit.chunk_id not in covered:
            out.append(hit)
    return out
