"""Worker: processa a fila de ingestão e entrega os eventos pendentes ao n8n.

Uso: python -m h2d.worker
Vários workers convivem sem pisar um no outro (SKIP LOCKED). A fila de ingestão é a própria tabela
de jobs, então o histórico e o motivo de cada falha ficam no mesmo lugar que a tela consulta. A
entrega ao n8n lê a tabela outbox_events.
"""

import asyncio
import logging
import time

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from h2d.config import get_settings
from h2d.db import get_sessionmaker
from h2d.kb.embeddings import Embedder, get_embedder
from h2d.kb.ingest import (
    IngestionError,
    claim_next_job,
    mark_failed,
    process_job,
    requeue_stale,
)
from h2d.models import IngestionJob
from h2d.outbox import deliver_pending

log = logging.getLogger("h2d.worker")
IDLE_SECONDS = 2.0
STALE_CHECK_SECONDS = 60.0


async def run_once(factory: async_sessionmaker[AsyncSession], embedder: Embedder) -> bool:
    """Processa no máximo um job. Devolve False quando a fila está vazia."""
    async with factory() as session, session.begin():
        job = await claim_next_job(session)
        if job is None:
            return False
        job_id = job.id

    try:
        async with factory() as session, session.begin():
            await process_job(session, await session.get_one(IngestionJob, job_id), embedder)
        log.info("job %s concluído", job_id)
    except Exception as error:
        # Erro de arquivo é definitivo; o resto (banco, memória) tenta de novo até o limite.
        final = isinstance(error, IngestionError)
        message = str(error) if final else f"{type(error).__name__}: {error}"
        log.warning("job %s falhou: %s", job_id, message)
        async with factory() as session, session.begin():
            await mark_failed(session, job_id, message, final=final)
    return True


async def deliver_outbox(
    factory: async_sessionmaker[AsyncSession], client: httpx.AsyncClient
) -> int:
    """Entrega os eventos pendentes ao n8n. Sem URL e segredo configurados, não faz nada."""
    settings = get_settings()
    secret = settings.n8n_hmac_secret
    if not settings.n8n_webhook_url or secret is None or not secret.get_secret_value():
        return 0
    async with factory() as session, session.begin():
        return await deliver_pending(
            session, client, url=settings.n8n_webhook_url, secret=secret.get_secret_value()
        )


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    factory = get_sessionmaker()
    embedder = get_embedder()
    last_stale_check = 0.0
    log.info("worker iniciado")
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            if time.monotonic() - last_stale_check > STALE_CHECK_SECONDS:
                async with factory() as session, session.begin():
                    if count := await requeue_stale(session):
                        log.warning("%d job(s) interrompido(s) voltaram à fila", count)
                last_stale_check = time.monotonic()
            worked = await run_once(factory, embedder)
            try:
                delivered = await deliver_outbox(factory, client)
            except Exception:  # a entrega nunca derruba a ingestão
                log.warning("falha ao entregar eventos ao n8n", exc_info=True)
                delivered = 0
            if not worked and not delivered:
                await asyncio.sleep(IDLE_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
