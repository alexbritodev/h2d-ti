"""Ingestão: registrar o envio, processar o job e publicar a versão.

Regras que os testes garantem:
- o mesmo arquivo (mesmo hash) não é processado de novo;
- a versão nova só vira ativa depois de pronta, e a anterior é arquivada na mesma transação;
- falha no meio do job não deixa trecho nem versão parcial ativa, e o motivo fica gravado;
- mudar a visibilidade do documento atualiza os trechos na mesma transação.
"""

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.kb.embeddings import Embedder, embed_async
from h2d.kb.parsing import ParsingError, to_markdown
from h2d.kb.text import chunk_markdown, sha256_hex, split_front_matter
from h2d.models import (
    IngestionJob,
    JobState,
    KbChunk,
    KbDocument,
    KbDocumentVersion,
    VersionStatus,
    Visibility,
)

# PDF e DOCX são lidos por extração de texto (h2d.kb.parsing). PDF digitalizado não tem OCR.
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf", ".docx"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ATTEMPTS = 3


class IngestionError(Exception):
    """Erro esperado e definitivo (arquivo ruim), com mensagem própria para aparecer na tela."""


@dataclass(frozen=True)
class Registered:
    document: KbDocument
    version: KbDocumentVersion
    job: IngestionJob | None
    duplicate: bool


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^\w.\- ]", "_", Path(name).name).strip(" .")
    return cleaned or "arquivo"


# Assinatura de cada formato binário: barra arquivo renomeado e envio quebrado antes de gravar.
_MAGIC = {".pdf": b"%PDF", ".docx": b"PK"}


def check_upload(filename: str, size: int, head: bytes = b"") -> None:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        aceitos = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise IngestionError(f"Formato {extension or 'desconhecido'} não suportado. Use: {aceitos}")
    if size == 0:
        raise IngestionError("O arquivo está vazio")
    if size > MAX_UPLOAD_BYTES:
        raise IngestionError(f"O arquivo passa de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    magic = _MAGIC.get(extension)
    if magic is not None and not head.startswith(magic):
        raise IngestionError(f"O arquivo não é um {extension.lstrip('.').upper()} válido")


async def register_upload(
    session: AsyncSession,
    *,
    upload_dir: str,
    actor_id: uuid.UUID | None,
    filename: str,
    data: bytes,
    title: str | None = None,
    visibility: Visibility | None = None,
    category: str | None = None,
    source: str | None = None,
    document_id: uuid.UUID | None = None,
) -> Registered:
    """Guarda o arquivo e enfileira o job. Arquivo repetido devolve o que já existe."""
    check_upload(filename, len(data), data[:8])
    sha = sha256_hex(data)

    duplicate_query = select(KbDocumentVersion).where(
        KbDocumentVersion.sha256 == sha, KbDocumentVersion.status != VersionStatus.FAILED
    )
    if document_id is not None:
        duplicate_query = duplicate_query.where(KbDocumentVersion.document_id == document_id)
    existing = await session.scalar(duplicate_query.limit(1))
    if existing is not None:
        document = await session.get_one(KbDocument, existing.document_id)
        return Registered(document, existing, None, duplicate=True)

    if document_id is None:
        meta, _ = split_front_matter(data.decode("utf-8", errors="replace"))
        # A visibilidade do cabeçalho do manual ("ti") só vale se ninguém escolheu outra.
        from_header = Visibility.IT if meta.get("visibilidade") == "ti" else Visibility.PUBLIC
        document = KbDocument(
            title=(title or meta.get("titulo") or Path(filename).stem).strip(),
            source=source,
            category=category or meta.get("categoria"),
            visibility=visibility or from_header,
            owner_id=actor_id,
        )
        session.add(document)
        await session.flush()
    else:
        document = await session.get_one(KbDocument, document_id)

    last = await session.scalar(
        select(func.max(KbDocumentVersion.version_number)).where(
            KbDocumentVersion.document_id == document.id
        )
    )
    path = Path(upload_dir) / str(uuid.uuid4()) / _safe_name(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    version = KbDocumentVersion(
        document_id=document.id,
        version_number=(last or 0) + 1,
        sha256=sha,
        original_filename=_safe_name(filename),
        size_bytes=len(data),
        file_path=str(path),
        status=VersionStatus.PROCESSING,
        created_by=actor_id,
    )
    session.add(version)
    await session.flush()
    job = IngestionJob(version_id=version.id, state=JobState.QUEUED)
    session.add(job)
    await session.flush()
    return Registered(document, version, job, duplicate=False)


async def enqueue_reindex(session: AsyncSession, version: KbDocumentVersion) -> IngestionJob:
    """Reprocessa uma versão (ex.: depois de trocar o modelo). A ativa segue valendo até lá."""
    job = IngestionJob(version_id=version.id, state=JobState.QUEUED)
    session.add(job)
    await session.flush()
    return job


async def claim_next_job(session: AsyncSession) -> IngestionJob | None:
    """Pega o próximo job da fila. SKIP LOCKED deixa vários workers conviverem sem pisar."""
    job = await session.scalar(
        select(IngestionJob)
        .where(IngestionJob.state == JobState.QUEUED)
        .order_by(IngestionJob.queued_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.state = JobState.RUNNING
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    job.finished_at = None
    await session.flush()
    return job


def _read_bytes(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise IngestionError(f"Não foi possível ler o arquivo enviado: {error}") from error


async def process_job(session: AsyncSession, job: IngestionJob, embedder: Embedder) -> None:
    """Lê, divide, embute e publica. Tudo ou nada: a publicação é uma transação só."""
    version = await session.get_one(KbDocumentVersion, job.version_id)
    document = await session.get_one(KbDocument, version.document_id)

    raw = await asyncio.to_thread(_read_bytes, version.file_path)
    try:
        # Ler PDF é trabalho de CPU: roda fora do laço de eventos.
        markdown = await asyncio.to_thread(to_markdown, version.original_filename, raw)
    except ParsingError as error:
        raise IngestionError(str(error)) from error
    _, body = split_front_matter(markdown)
    chunks = chunk_markdown(body, title=document.title)
    if not chunks:
        raise IngestionError("Não encontrei texto no arquivo")

    vectors = await embed_async(embedder, [f"{c.breadcrumb}\n{c.content}" for c in chunks])

    # Reprocessar (reindexação) começa limpo: nunca duplica trechos da mesma versão.
    await session.execute(delete(KbChunk).where(KbChunk.version_id == version.id))
    session.add_all(
        KbChunk(
            version_id=version.id,
            document_id=document.id,
            position=chunk.position,
            content=chunk.content,
            breadcrumb=chunk.breadcrumb,
            embedding=vector,
            embedding_model=embedder.model_name,
            visibility=document.visibility,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    )
    await session.flush()

    # Publicação: a anterior sai e a nova entra na mesma transação, nunca as duas nem nenhuma.
    previous = (
        await session.scalars(
            select(KbDocumentVersion).where(
                KbDocumentVersion.document_id == document.id,
                KbDocumentVersion.status == VersionStatus.ACTIVE,
                KbDocumentVersion.id != version.id,
            )
        )
    ).all()
    for old in previous:
        old.status = VersionStatus.ARCHIVED
        await session.execute(delete(KbChunk).where(KbChunk.version_id == old.id))
    await session.flush()
    version.status = VersionStatus.ACTIVE
    version.markdown = body
    version.error = None
    version.published_at = datetime.now(UTC)
    job.state = JobState.SUCCEEDED
    job.error = None
    job.finished_at = datetime.now(UTC)


async def mark_failed(session: AsyncSession, job_id: uuid.UUID, error: str, *, final: bool) -> None:
    """Grava a falha numa transação limpa. Erro inesperado tenta de novo até MAX_ATTEMPTS.

    Uma versão que já estava ativa nunca é tocada aqui, só a que estava em processamento.
    """
    job = await session.get_one(IngestionJob, job_id)
    version = await session.get_one(KbDocumentVersion, job.version_id)
    retry = not final and job.attempts < MAX_ATTEMPTS
    job.error = error[:2000]
    job.finished_at = datetime.now(UTC)
    job.state = JobState.QUEUED if retry else JobState.FAILED
    if not retry and version.status == VersionStatus.PROCESSING:
        version.status = VersionStatus.FAILED
        version.error = job.error


async def set_visibility(
    session: AsyncSession, document: KbDocument, visibility: Visibility
) -> None:
    """Documento e trechos mudam juntos: nenhum trecho restrito pode sobrar como público."""
    document.visibility = visibility
    await session.execute(
        update(KbChunk).where(KbChunk.document_id == document.id).values(visibility=visibility)
    )


STALE_AFTER = timedelta(minutes=15)


async def requeue_stale(session: AsyncSession) -> int:
    """Job preso em "running" (worker que caiu) volta à fila, ou falha se já tentou demais."""
    limit = datetime.now(UTC) - STALE_AFTER
    stale = (
        await session.scalars(
            select(IngestionJob).where(
                IngestionJob.state == JobState.RUNNING, IngestionJob.started_at < limit
            )
        )
    ).all()
    for job in stale:
        await mark_failed(session, job.id, "O processamento foi interrompido", final=False)
    return len(stale)
