"""Base de conhecimento: envio e acompanhamento da ingestão (admin) e busca (quem está logado)."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from h2d.config import get_settings
from h2d.deps import CurrentUser, SessionDep, require_role
from h2d.kb.embeddings import Embedder, get_embedder
from h2d.kb.ingest import (
    MAX_UPLOAD_BYTES,
    IngestionError,
    enqueue_reindex,
    register_upload,
    set_visibility,
)
from h2d.kb.search import search_chunks
from h2d.models import (
    AuditLog,
    IngestionJob,
    JobState,
    KbChunk,
    KbDocument,
    KbDocumentVersion,
    Role,
    User,
    VersionStatus,
    Visibility,
)

router = APIRouter(prefix="/kb", tags=["kb"])

AdminActor = Annotated[User, Depends(require_role(Role.ADMIN))]


def get_embedder_dep() -> Embedder:
    return get_embedder()


EmbedderDep = Annotated[Embedder, Depends(get_embedder_dep)]


def _can_see_it(user: User) -> bool:
    return user.role in (Role.TECH, Role.ADMIN)


class UploadOut(BaseModel):
    document_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID | None
    duplicate: bool


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    category: str | None
    visibility: Visibility
    valid_until: date | None
    updated_at: datetime
    version_number: int | None
    version_status: VersionStatus | None
    filename: str | None
    size_bytes: int | None
    error: str | None
    published_at: datetime | None


class DocumentUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    visibility: Visibility | None = None


class JobOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    filename: str
    version_number: int
    state: JobState
    attempts: int
    error: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class HitOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    breadcrumb: str
    content: str
    score: float


class LibraryItem(BaseModel):
    id: uuid.UUID
    title: str
    category: str | None
    visibility: Visibility
    published_at: datetime | None


@router.post("/documents", status_code=status.HTTP_201_CREATED, operation_id="uploadDocument")
async def upload_document(
    session: SessionDep,
    actor: AdminActor,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
    visibility: Annotated[Visibility | None, Form()] = None,
    document_id: Annotated[uuid.UUID | None, Form()] = None,
) -> UploadOut:
    # Lê um byte além do limite para recusar sem carregar um arquivo gigante inteiro.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if document_id is not None and await session.get(KbDocument, document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    try:
        result = await register_upload(
            session,
            upload_dir=get_settings().upload_dir,
            actor_id=actor.id,
            filename=file.filename or "arquivo",
            data=data,
            title=title,
            category=category,
            visibility=visibility,
            document_id=document_id,
        )
    except IngestionError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    if not result.duplicate:
        session.add(
            AuditLog(
                actor_id=actor.id,
                action="kb.upload",
                entity_type="kb_document",
                entity_id=str(result.document.id),
                after={
                    "filename": result.version.original_filename,
                    "version": result.version.version_number,
                },
            )
        )
    await session.commit()
    return UploadOut(
        document_id=result.document.id,
        version_id=result.version.id,
        job_id=result.job.id if result.job else None,
        duplicate=result.duplicate,
    )


@router.get("/documents", operation_id="listDocuments")
async def list_documents(session: SessionDep, _: AdminActor) -> list[DocumentOut]:
    documents = (
        await session.scalars(select(KbDocument).order_by(KbDocument.updated_at.desc()))
    ).all()
    versions = (
        await session.scalars(
            select(KbDocumentVersion).order_by(KbDocumentVersion.version_number.desc())
        )
    ).all()
    latest: dict[uuid.UUID, KbDocumentVersion] = {}
    for version in versions:
        current = latest.get(version.document_id)
        # A ativa mostra o que vale; sem ativa, a mais recente (em processamento ou com falha).
        if current is None or (
            version.status is VersionStatus.ACTIVE and current.status is not VersionStatus.ACTIVE
        ):
            latest[version.document_id] = version
    out = []
    for document in documents:
        version = latest.get(document.id)
        out.append(
            DocumentOut(
                id=document.id,
                title=document.title,
                category=document.category,
                visibility=document.visibility,
                valid_until=document.valid_until,
                updated_at=document.updated_at,
                version_number=version.version_number if version else None,
                version_status=version.status if version else None,
                filename=version.original_filename if version else None,
                size_bytes=version.size_bytes if version else None,
                error=version.error if version else None,
                published_at=version.published_at if version else None,
            )
        )
    return out


@router.patch("/documents/{document_id}", operation_id="updateDocument")
async def update_document(
    document_id: uuid.UUID, body: DocumentUpdate, session: SessionDep, actor: AdminActor
) -> DocumentOut:
    document = await session.get(KbDocument, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    before = {
        "title": document.title,
        "category": document.category,
        "visibility": document.visibility.value,
    }
    if body.title is not None and body.title.strip():
        document.title = body.title.strip()
    if body.category is not None:
        document.category = body.category.strip() or None
    if body.visibility is not None and body.visibility is not document.visibility:
        # Documento e trechos mudam na mesma transação: nada restrito sobra como público.
        await set_visibility(session, document, body.visibility)
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="kb.update",
            entity_type="kb_document",
            entity_id=str(document.id),
            before=before,
            after={
                "title": document.title,
                "category": document.category,
                "visibility": document.visibility.value,
            },
        )
    )
    await session.commit()
    return next(d for d in await list_documents(session, actor) if d.id == document.id)


@router.post(
    "/documents/{document_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="reindexDocument",
)
async def reindex_document(document_id: uuid.UUID, session: SessionDep, _: AdminActor) -> UploadOut:
    version = await session.scalar(
        select(KbDocumentVersion)
        .where(KbDocumentVersion.document_id == document_id)
        .order_by(KbDocumentVersion.version_number.desc())
        .limit(1)
    )
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    job = await enqueue_reindex(session, version)
    await session.commit()
    return UploadOut(document_id=document_id, version_id=version.id, job_id=job.id, duplicate=False)


@router.get("/jobs", operation_id="listIngestionJobs")
async def list_jobs(
    session: SessionDep, _: AdminActor, limit: int = Query(50, ge=1, le=200)
) -> list[JobOut]:
    rows = await session.execute(
        select(IngestionJob, KbDocumentVersion, KbDocument)
        .join(KbDocumentVersion, KbDocumentVersion.id == IngestionJob.version_id)
        .join(KbDocument, KbDocument.id == KbDocumentVersion.document_id)
        .order_by(IngestionJob.queued_at.desc())
        .limit(limit)
    )
    return [
        JobOut(
            id=job.id,
            document_id=document.id,
            document_title=document.title,
            filename=version.original_filename,
            version_number=version.version_number,
            state=job.state,
            attempts=job.attempts,
            error=job.error,
            queued_at=job.queued_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )
        for job, version, document in rows
    ]


@router.get("/search", operation_id="searchKnowledge")
async def search(
    session: SessionDep,
    user: CurrentUser,
    embedder: EmbedderDep,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[HitOut]:
    hits = await search_chunks(session, q, embedder, can_see_it=_can_see_it(user), limit=limit)
    return [
        HitOut(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            document_title=h.document_title,
            breadcrumb=h.breadcrumb,
            content=h.content,
            score=h.score,
        )
        for h in hits
    ]


@router.get("/chunks/{chunk_id}", operation_id="getChunk")
async def get_chunk(chunk_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> HitOut:
    """Trecho citado, para abrir a fonte. Trecho restrito responde 404, como se não existisse."""
    chunk = await session.get(KbChunk, chunk_id)
    version = await session.get(KbDocumentVersion, chunk.version_id) if chunk else None
    if (
        chunk is None
        or version is None
        or version.status is not VersionStatus.ACTIVE
        or (chunk.visibility is Visibility.IT and not _can_see_it(user))
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trecho não encontrado")
    document = await session.get_one(KbDocument, chunk.document_id)
    return HitOut(
        chunk_id=chunk.id,
        document_id=document.id,
        document_title=document.title,
        breadcrumb=chunk.breadcrumb,
        content=chunk.content,
        score=0.0,
    )


@router.get("/library", operation_id="listLibrary")
async def library(session: SessionDep, user: CurrentUser) -> list[LibraryItem]:
    """Documentos publicados que a pessoa pode ver (base de conhecimento para o usuário)."""
    query = (
        select(KbDocument, KbDocumentVersion.published_at)
        .join(KbDocumentVersion, KbDocumentVersion.document_id == KbDocument.id)
        .where(KbDocumentVersion.status == VersionStatus.ACTIVE)
        .order_by(KbDocument.title)
    )
    if not _can_see_it(user):
        query = query.where(KbDocument.visibility == Visibility.PUBLIC)
    return [
        LibraryItem(
            id=d.id,
            title=d.title,
            category=d.category,
            visibility=d.visibility,
            published_at=published_at,
        )
        for d, published_at in await session.execute(query)
    ]
