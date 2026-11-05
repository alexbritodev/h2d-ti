"""Cria o primeiro administrador, inclusive em produção.

Uso: ADMIN_EMAIL=... ADMIN_NAME=... ADMIN_PASSWORD=... python -m h2d.create_admin

Diferente do seed, não cria dados de demonstração e recusa senha curta. Se o e-mail já
existe, não altera nada: trocar senha de quem já existe não é função deste comando.
"""

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.db import get_sessionmaker
from h2d.models import Role, User
from h2d.security import check_password_policy, hash_password


class CreateAdminError(RuntimeError):
    pass


async def create_admin(session: AsyncSession, *, email: str, name: str, password: str) -> bool:
    """Devolve True se criou e False se o e-mail já existia."""
    email = email.strip().lower()
    if "@" not in email:
        raise CreateAdminError("ADMIN_EMAIL precisa ser um e-mail válido")
    if not name.strip():
        raise CreateAdminError("ADMIN_NAME não pode ficar vazio")
    try:
        check_password_policy(password)
    except ValueError as error:
        raise CreateAdminError(f"ADMIN_PASSWORD inválida: {error}") from error

    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        return False
    session.add(
        User(
            name=name.strip(),
            email=email,
            password_hash=hash_password(password),
            role=Role.ADMIN,
            department="TI",
        )
    )
    await session.flush()
    return True


async def _main() -> None:
    values = {
        key: os.environ.get(key, "") for key in ("ADMIN_EMAIL", "ADMIN_NAME", "ADMIN_PASSWORD")
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise CreateAdminError(f"Defina {', '.join(missing)}")
    async with get_sessionmaker()() as session, session.begin():
        created = await create_admin(
            session,
            email=values["ADMIN_EMAIL"],
            name=values["ADMIN_NAME"],
            password=values["ADMIN_PASSWORD"],
        )
    print("Administrador criado." if created else "Esse e-mail já existe; nada foi alterado.")


if __name__ == "__main__":
    asyncio.run(_main())
