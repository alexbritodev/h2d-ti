from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.kb.embeddings import FakeEmbedder
from h2d.kb.ingest import (
    IngestionError,
    claim_next_job,
    enqueue_reindex,
    mark_failed,
    process_job,
    register_upload,
    set_visibility,
)
from h2d.kb.search import search_chunks
from h2d.models import (
    IngestionJob,
    JobState,
    KbChunk,
    KbDocument,
    KbDocumentVersion,
    VersionStatus,
    Visibility,
)

VPN = """---
titulo: VPN corporativa
categoria: Redes
visibilidade: publico
---

# VPN

## Sessão

A sessão da VPN dura 12 horas e depois é preciso conectar de novo.

## Erros

Quando aparece servidor não responde, teste outra rede.
"""

SEGURANCA = """---
titulo: Resposta a incidentes
categoria: Segurança
visibilidade: ti
---

# Incidentes

## Prazos

O prazo da primeira resposta a um incidente crítico é de 15 minutos.
"""


class BoomEmbedder(FakeEmbedder):
    def embed(self, texts):
        raise RuntimeError("memória esgotada")


async def _ingest(session: AsyncSession, tmp_path: Path, name: str, text: str, **kwargs):
    registered = await register_upload(
        session,
        upload_dir=str(tmp_path),
        actor_id=None,
        filename=name,
        data=text.encode(),
        **kwargs,
    )
    await session.commit()
    return registered


async def _run(session: AsyncSession, embedder=None) -> IngestionJob:
    job = await claim_next_job(session)
    assert job is not None
    await process_job(session, job, embedder or FakeEmbedder())
    await session.commit()
    return job


async def test_envio_cria_documento_versao_e_job_e_le_a_visibilidade_do_cabecalho(
    session, tmp_path
):
    registered = await _ingest(session, tmp_path, "seg.md", SEGURANCA)

    assert registered.duplicate is False
    assert registered.document.title == "Resposta a incidentes"
    assert registered.document.visibility is Visibility.IT
    assert registered.version.status is VersionStatus.PROCESSING
    assert registered.job is not None and registered.job.state is JobState.QUEUED
    gravado = Path(registered.version.file_path).read_text(encoding="utf-8")  # noqa: ASYNC240
    assert gravado == SEGURANCA


async def test_visibilidade_escolhida_vale_mais_que_a_do_cabecalho(session, tmp_path):
    registered = await _ingest(session, tmp_path, "vpn.md", VPN, visibility=Visibility.IT)

    assert registered.document.visibility is Visibility.IT


async def test_mesmo_arquivo_nao_reprocessa(session, tmp_path):
    first = await _ingest(session, tmp_path, "vpn.md", VPN)
    await _run(session)

    again = await _ingest(session, tmp_path, "copia-da-vpn.md", VPN)

    assert again.duplicate is True
    assert again.job is None
    assert again.version.id == first.version.id
    assert await session.scalar(select(func.count()).select_from(IngestionJob)) == 1
    assert await session.scalar(select(func.count()).select_from(KbDocumentVersion)) == 1


@pytest.mark.parametrize(
    ("nome", "tamanho"), [("manual.exe", 10), ("vazio.md", 0), ("grande.md", 11 * 1024 * 1024)]
)
async def test_arquivo_invalido_e_recusado(session, tmp_path, nome, tamanho):
    with pytest.raises(IngestionError):
        await register_upload(
            session,
            upload_dir=str(tmp_path),
            actor_id=None,
            filename=nome,
            data=b"x" * tamanho,
        )


async def test_processar_publica_trechos_e_ativa_a_versao(session, tmp_path):
    registered = await _ingest(session, tmp_path, "vpn.md", VPN)

    job = await _run(session)

    await session.refresh(registered.version)
    assert job.state is JobState.SUCCEEDED
    assert registered.version.status is VersionStatus.ACTIVE
    assert registered.version.published_at is not None
    chunks = (await session.scalars(select(KbChunk).order_by(KbChunk.position))).all()
    assert [c.breadcrumb for c in chunks] == [
        "VPN corporativa > VPN > Sessão",
        "VPN corporativa > VPN > Erros",
    ]
    assert all(c.visibility is Visibility.PUBLIC for c in chunks)
    assert all(len(c.embedding) == 384 for c in chunks)


async def test_versao_nova_arquiva_a_anterior_so_depois_de_publicada(session, tmp_path):
    first = await _ingest(session, tmp_path, "vpn.md", VPN)
    await _run(session)
    second = await _ingest(
        session,
        tmp_path,
        "vpn-v2.md",
        VPN + "\n## Novo\n\nTexto novo da versão dois.\n",
        document_id=first.document.id,
    )

    # Enquanto a nova não foi processada, a anterior continua valendo.
    await session.refresh(first.version)
    assert first.version.status is VersionStatus.ACTIVE
    assert second.version.version_number == 2

    await _run(session)

    await session.refresh(first.version)
    await session.refresh(second.version)
    assert first.version.status is VersionStatus.ARCHIVED
    assert second.version.status is VersionStatus.ACTIVE
    chunk_versions = set(await session.scalars(select(KbChunk.version_id)))
    assert chunk_versions == {second.version.id}


async def test_falha_no_meio_nao_deixa_versao_parcial_nem_derruba_a_anterior(session, tmp_path):
    first = await _ingest(session, tmp_path, "vpn.md", VPN)
    await _run(session)
    second = await _ingest(
        session,
        tmp_path,
        "vpn-v2.md",
        VPN + "\n## Novo\n\nOutro texto.\n",
        document_id=first.document.id,
    )

    job = await claim_next_job(session)
    assert job is not None
    await session.commit()
    job_id = job.id
    with pytest.raises(RuntimeError):
        await process_job(session, job, BoomEmbedder())
    await session.rollback()
    await mark_failed(session, job_id, "RuntimeError: memória esgotada", final=True)
    await session.commit()

    await session.refresh(first.version)
    await session.refresh(second.version)
    failed = await session.get_one(IngestionJob, job_id)
    assert failed.state is JobState.FAILED
    assert "memória esgotada" in (failed.error or "")
    assert second.version.status is VersionStatus.FAILED
    assert first.version.status is VersionStatus.ACTIVE
    assert (
        await session.scalar(
            select(func.count()).select_from(KbChunk).where(KbChunk.version_id == second.version.id)
        )
        == 0
    )


async def test_falha_inesperada_volta_para_a_fila_ate_o_limite(session, tmp_path):
    await _ingest(session, tmp_path, "vpn.md", VPN)
    for tentativa in (1, 2, 3):
        job = await claim_next_job(session)
        assert job is not None and job.attempts == tentativa
        await mark_failed(session, job.id, "RuntimeError: banco caiu", final=False)
        await session.commit()
        await session.refresh(job)

    assert job.state is JobState.FAILED
    assert await claim_next_job(session) is None


async def test_arquivo_sem_texto_falha_com_motivo_definitivo(session, tmp_path):
    await _ingest(session, tmp_path, "vazio.md", "---\ntitulo: Vazio\n---\n\n## Só título\n")
    job = await claim_next_job(session)
    assert job is not None
    await session.commit()

    with pytest.raises(IngestionError, match="texto"):
        await process_job(session, job, FakeEmbedder())


async def test_reindexar_nao_duplica_trechos(session, tmp_path):
    registered = await _ingest(session, tmp_path, "vpn.md", VPN)
    await _run(session)
    antes = await session.scalar(select(func.count()).select_from(KbChunk))

    await enqueue_reindex(session, registered.version)
    await session.commit()
    await _run(session)

    assert await session.scalar(select(func.count()).select_from(KbChunk)) == antes
    await session.refresh(registered.version)
    assert registered.version.status is VersionStatus.ACTIVE


# --- Busca e permissão ---------------------------------------------------------------------------


async def _base_com_publico_e_restrito(session, tmp_path):
    await _ingest(session, tmp_path, "vpn.md", VPN)
    await _ingest(session, tmp_path, "seg.md", SEGURANCA)
    await _run(session)
    await _run(session)


async def test_busca_acha_o_trecho_certo(session, tmp_path):
    await _base_com_publico_e_restrito(session, tmp_path)

    hits = await search_chunks(
        session, "quanto tempo dura a sessão da VPN", FakeEmbedder(), can_see_it=False
    )

    assert hits
    assert "12 horas" in hits[0].content
    assert hits[0].document_title == "VPN corporativa"


async def test_usuario_comum_nunca_recebe_trecho_restrito_a_ti(session, tmp_path):
    await _base_com_publico_e_restrito(session, tmp_path)
    pergunta = "prazo da primeira resposta a um incidente crítico 15 minutos"

    comum = await search_chunks(session, pergunta, FakeEmbedder(), can_see_it=False)
    tecnico = await search_chunks(session, pergunta, FakeEmbedder(), can_see_it=True)

    assert all(h.visibility == "public" for h in comum)
    assert all("Resposta a incidentes" not in h.document_title for h in comum)
    assert any("15 minutos" in h.content for h in tecnico)


async def test_mudar_visibilidade_atualiza_os_trechos_na_mesma_transacao(session, tmp_path):
    await _base_com_publico_e_restrito(session, tmp_path)
    pergunta = "quanto tempo dura a sessão da VPN"
    assert await search_chunks(session, pergunta, FakeEmbedder(), can_see_it=False)

    vpn = (
        await session.scalars(select(KbDocument).where(KbDocument.title == "VPN corporativa"))
    ).one()
    await set_visibility(session, vpn, Visibility.IT)
    await session.commit()

    assert await search_chunks(session, pergunta, FakeEmbedder(), can_see_it=False) == []
    assert await search_chunks(session, pergunta, FakeEmbedder(), can_see_it=True)
    restantes = await session.scalar(
        select(func.count()).select_from(KbChunk).where(KbChunk.visibility == Visibility.PUBLIC)
    )
    assert restantes == 0


async def test_versao_arquivada_nao_aparece_na_busca(session, tmp_path):
    first = await _ingest(session, tmp_path, "vpn.md", VPN)
    await _run(session)
    await _ingest(
        session,
        tmp_path,
        "vpn-v2.md",
        VPN.replace("12 horas", "8 horas"),
        document_id=first.document.id,
    )
    await _run(session)

    hits = await search_chunks(
        session, "quanto tempo dura a sessão da VPN", FakeEmbedder(), can_see_it=False
    )

    assert hits and "8 horas" in hits[0].content
    assert all("12 horas" not in h.content for h in hits)


async def test_pergunta_vazia_ou_so_de_palavras_curtas_nao_quebra(session, tmp_path):
    await _base_com_publico_e_restrito(session, tmp_path)

    assert await search_chunks(session, "   ", FakeEmbedder(), can_see_it=False) == []
    await search_chunks(session, "a o e", FakeEmbedder(), can_see_it=False)
