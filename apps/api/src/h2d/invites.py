"""Convite por e-mail: o link leva a pessoa a definir a própria senha.

O token nasce aleatório (256 bits) e só o hash dele fica no banco. O e-mail sai pelo mesmo outbox
do n8n; depois da entrega o token é apagado do evento (ver `outbox.py`).
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.config import get_settings
from h2d.models import OutboxEvent, User, UserInvite

EVENT_TYPE = "user.invited"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_invite(session: AsyncSession, user: User, *, now: datetime | None = None) -> None:
    """Gera um link novo e enfileira o e-mail. Os links anteriores ainda abertos deixam de valer."""
    now = now or datetime.now(UTC)
    ttl_hours = get_settings().invite_ttl_hours
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(hours=ttl_hours)

    await session.execute(
        delete(UserInvite).where(UserInvite.user_id == user.id, UserInvite.used_at.is_(None))
    )
    session.add(UserInvite(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    session.add(
        OutboxEvent(
            type=EVENT_TYPE,
            payload={
                "name": user.name,
                "email": user.email,
                "token": token,
                "expires_at": expires_at.isoformat(),
                "valid_hours": ttl_hours,
            },
        )
    )


async def find_valid_invite(
    session: AsyncSession, token: str, *, now: datetime | None = None
) -> tuple[UserInvite, User] | None:
    """O convite e a pessoa, se o link existe, não foi usado e não venceu."""
    now = now or datetime.now(UTC)
    invite = await session.scalar(
        select(UserInvite).where(UserInvite.token_hash == hash_token(token))
    )
    if invite is None or invite.used_at is not None or invite.expires_at <= now:
        return None
    user = await session.get(User, invite.user_id)
    if user is None or not user.is_active:
        return None
    return invite, user


async def pending_user_ids(session: AsyncSession, *, now: datetime | None = None) -> set[uuid.UUID]:
    """Quem tem convite aberto (nem usado, nem vencido)."""
    now = now or datetime.now(UTC)
    rows = await session.scalars(
        select(UserInvite.user_id).where(UserInvite.used_at.is_(None), UserInvite.expires_at > now)
    )
    return set(rows)
