import uuid

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from h2d.config import get_settings
from h2d.deps import SESSION_COOKIE, CurrentUser, SessionDep
from h2d.models import Role, User
from h2d.security import (
    burn_verification_time,
    create_session_token,
    hash_password,
    needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_PATH = "/api"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    # O limite evita gastar CPU do argon2 com entradas enormes.
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role
    department: str | None


@router.post("/login", operation_id="login")
async def login(body: LoginRequest, session: SessionDep, response: Response) -> UserOut:
    email = body.email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))

    if user is None:
        burn_verification_time(body.password)
        authenticated = False
    else:
        authenticated = verify_password(user.password_hash, body.password) and user.is_active

    # A mesma resposta em todos os casos: não revela se o e-mail existe nem se está ativo.
    if user is None or not authenticated:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        await session.commit()

    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id),
        max_age=settings.jwt_ttl_minutes * 60,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, operation_id="logout")
async def logout(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path=_COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )


@router.get("/me", operation_id="getMe")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
