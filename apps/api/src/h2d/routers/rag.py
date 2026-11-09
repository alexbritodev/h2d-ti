"""Painel do RAG (só administrador): rastreia a busca, abre um trecho e resume o pipeline.

Nada aqui chama o modelo de linguagem nem grava dados.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from h2d.deps import SessionDep, require_role
from h2d.kb.embeddings import Embedder, get_embedder
from h2d.kb.rag_trace import (
    ChunkAnatomy,
    OverviewOut,
    TraceOut,
    chunk_anatomy,
    overview,
    trace_question,
)
from h2d.models import Role, User

AdminActor = Annotated[User, Depends(require_role(Role.ADMIN))]

router = APIRouter(prefix="/admin/rag", tags=["rag"])


def get_embedder_dep() -> Embedder:
    return get_embedder()


EmbedderDep = Annotated[Embedder, Depends(get_embedder_dep)]


class TraceIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@router.get("/overview", operation_id="getRagOverview")
async def get_overview(session: SessionDep, _: AdminActor, embedder: EmbedderDep) -> OverviewOut:
    return await overview(session, embedder)


@router.post("/trace", operation_id="traceRag")
async def trace(
    body: TraceIn, session: SessionDep, _: AdminActor, embedder: EmbedderDep
) -> TraceOut:
    return await trace_question(session, embedder, body.question)


@router.get("/chunks/{chunk_id}", operation_id="getRagChunk")
async def get_chunk(
    chunk_id: uuid.UUID, session: SessionDep, _: AdminActor, embedder: EmbedderDep
) -> ChunkAnatomy:
    anatomy = await chunk_anatomy(session, embedder, chunk_id)
    if anatomy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trecho não encontrado")
    return anatomy
