from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.kb.embeddings import FakeEmbedder
from h2d.kb.ingest import claim_next_job, process_job, register_upload
from h2d.kb.search import expand_sections, search_chunks

PASSOS = "\n".join(
    f"{n}. Passo {n} do procedimento: faça a ação {n} e confira o resultado na tela do sistema."
    for n in range(1, 9)
)
MANUAL = f"""---
titulo: Manual de contas
categoria: Linux
visibilidade: publico
---

## Criar usuário

{PASSOS}
"""


async def _ingest(session: AsyncSession, tmp_path: Path, doc: str) -> None:
    await register_upload(
        session, upload_dir=str(tmp_path), actor_id=None, filename="m.md", data=doc.encode()
    )
    await session.commit()
    while (job := await claim_next_job(session)) is not None:
        await process_job(session, job, FakeEmbedder())
        await session.commit()


async def test_usuario_sem_acento_casa_com_usuario_com_acento(session: AsyncSession):
    casou = await session.scalar(
        text(
            "SELECT to_tsvector('portuguese', h2d_unaccent('Criar usuário e senhas')) "
            "@@ to_tsquery('portuguese', h2d_unaccent('usuario | senha'))"
        )
    )
    assert casou is True


async def test_chunks_guardam_o_tsvector_sem_acento(session: AsyncSession, tmp_path: Path):
    await _ingest(session, tmp_path, MANUAL)

    achou = await session.scalar(
        text(
            "SELECT count(*) FROM kb_chunks "
            "WHERE tsv @@ to_tsquery('portuguese', h2d_unaccent('usuario'))"
        )
    )

    assert achou and achou >= 1


async def test_trecho_achado_vem_com_os_vizinhos_da_mesma_secao(
    session: AsyncSession, tmp_path: Path
):
    await _ingest(session, tmp_path, MANUAL)
    [hit] = await search_chunks(
        session, "Passo 1 do procedimento", FakeEmbedder(), can_see_it=True, limit=1
    )

    [expanded] = await expand_sections(session, [hit], can_see_it=True)

    assert len(expanded.content) > len(hit.content)
    assert expanded.chunk_id == hit.chunk_id  # a citação continua apontando o trecho achado
    assert "Passo 1" in expanded.content
