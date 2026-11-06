"""Fila de eventos para o n8n (padrão outbox) e a assinatura HMAC dos dois sentidos.

O evento nasce na mesma transação do dado que o originou. Este módulo só entrega: tenta, espera
mais a cada falha e desiste depois de MAX_ATTEMPTS. O `event_id` vai em cada tentativa, então o
n8n descarta repetidos e a reentrega nunca duplica aviso.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.models import OutboxEvent, OutboxStatus

MAX_ATTEMPTS = 10
BATCH = 10
TOLERANCE_SECONDS = 300


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """Assinatura sobre "<horário>.<corpo>": o horário entra para barrar reenvio antigo."""
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def verify(
    secret: str, timestamp: str, body: bytes, signature: str, *, now: datetime | None = None
) -> bool:
    try:
        sent_at = int(timestamp)
    except ValueError:
        return False
    current = int((now or datetime.now(UTC)).timestamp())
    if abs(current - sent_at) > TOLERANCE_SECONDS:
        return False
    return hmac.compare_digest(sign(secret, timestamp, body), signature)


def _body(event: OutboxEvent) -> bytes:
    return json.dumps(
        {
            "event_id": str(event.event_id),
            "type": event.type,
            "created_at": event.created_at.isoformat(),
            "payload": event.payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * 2 ** (attempts - 1), 3600))


async def deliver_pending(
    session: AsyncSession,
    client: httpx.AsyncClient,
    *,
    url: str,
    secret: str,
    now: datetime | None = None,
) -> int:
    """Entrega os eventos vencidos. Devolve quantos foram tentados."""
    now = now or datetime.now(UTC)
    events = (
        await session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.PENDING, OutboxEvent.next_attempt_at <= now)
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(BATCH)
        )
    ).all()
    for event in events:
        body = _body(event)
        timestamp = str(int(now.timestamp()))
        headers = {
            "Content-Type": "application/json",
            "X-H2D-Timestamp": timestamp,
            "X-H2D-Signature": sign(secret, timestamp, body),
            "X-H2D-Event-Id": str(event.event_id),
            "X-H2D-Event-Type": event.type,
        }
        error: str | None = None
        try:
            response = await client.post(url, content=body, headers=headers)
            if not 200 <= response.status_code < 300:
                error = f"HTTP {response.status_code}: {response.text[:200]}"
        except httpx.HTTPError as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
        event.attempts += 1
        if error is None:
            event.status = OutboxStatus.DELIVERED
            event.delivered_at = now
            event.last_error = None
            if "token" in event.payload:
                # O link já foi enviado: o segredo não precisa ficar guardado no banco.
                event.payload = {**event.payload, "token": None}
        else:
            event.last_error = error
            if event.attempts >= MAX_ATTEMPTS:
                event.status = OutboxStatus.FAILED
            else:
                event.next_attempt_at = now + _backoff(event.attempts)
    await session.flush()
    return len(events)
