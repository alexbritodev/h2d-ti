from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from h2d.db import get_session
from h2d.models import Role, User
from h2d.security import read_session_token

SESSION_COOKIE = "h2d_session"

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    h2d_session: Annotated[str | None, Cookie()] = None,
) -> User:
    unauthenticated = HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    if h2d_session is None:
        raise unauthenticated
    user_id = read_session_token(h2d_session)
    if user_id is None:
        raise unauthenticated
    # Consulta o banco a cada requisição para que desativar um usuário valha na hora.
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthenticated
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[..., Awaitable[User]]:
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão")
        return user

    return checker
