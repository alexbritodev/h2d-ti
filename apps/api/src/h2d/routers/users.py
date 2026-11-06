"""Gestão de usuários. Tudo aqui é só para administradores e deixa rastro em audit_log."""

import secrets
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from h2d.deps import SessionDep, require_role
from h2d.invites import create_invite, pending_user_ids
from h2d.models import AuditLog, Role, User
from h2d.security import check_password_policy, hash_password

# Toda rota deste módulo exige administrador. O ator fica disponível para a auditoria.
AdminActor = Annotated[User, Depends(require_role(Role.ADMIN))]

router = APIRouter(prefix="/users", tags=["users"])


class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role
    department: str | None
    is_vip: bool
    is_active: bool
    created_at: datetime
    # Tem um link de acesso enviado, ainda válido e não usado.
    invite_pending: bool = False


def _check_email(value: str) -> str:
    value = value.strip()
    local, _, domain = value.partition("@")
    if not local or "." not in domain or " " in value:
        raise ValueError("Informe um e-mail válido")
    return value


class _PasswordMixin(BaseModel):
    # O limite superior evita gastar CPU do argon2 com entradas enormes.
    password: str = Field(max_length=1024)

    @field_validator("password")
    @classmethod
    def _policy(cls, value: str) -> str:
        return check_password_policy(value)


class UserCreate(_PasswordMixin):
    name: str = Field(min_length=1, max_length=200)
    # Sem EmailStr: ele recusa domínios como .local, que o seed e a rede interna usam.
    email: str = Field(min_length=3, max_length=320)
    role: Role = Role.USER
    department: str | None = Field(default=None, max_length=120)
    is_vip: bool = False

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        return _check_email(value)


class UserInviteCreate(BaseModel):
    """Convite: a pessoa define a própria senha pelo link enviado ao e-mail."""

    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    role: Role = Role.USER
    department: str | None = Field(default=None, max_length=120)
    is_vip: bool = False

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        return _check_email(value)


class UserUpdate(BaseModel):
    """Só os campos enviados mudam. O e-mail não muda: ele identifica a pessoa no histórico."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    department: str | None = Field(default=None, max_length=120)
    is_vip: bool | None = None
    is_active: bool | None = None


class PasswordReset(_PasswordMixin):
    pass


def _snapshot(user: User) -> dict[str, Any]:
    """Estado gravado na auditoria. Nunca inclui a senha nem o hash."""
    return {
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "department": user.department,
        "is_vip": user.is_vip,
        "is_active": user.is_active,
    }


@router.get("", operation_id="listUsers")
async def list_users(
    session: SessionDep,
    _: AdminActor,
    role: Role | None = None,
    status_filter: Literal["active", "inactive"] | None = None,
) -> list[UserAdminOut]:
    query = select(User).order_by(func.lower(User.name))
    if role is not None:
        query = query.where(User.role == role)
    if status_filter is not None:
        query = query.where(User.is_active == (status_filter == "active"))
    pending = await pending_user_ids(session)
    users = []
    for user in await session.scalars(query):
        out = UserAdminOut.model_validate(user)
        out.invite_pending = user.id in pending
        users.append(out)
    return users


@router.post("", status_code=status.HTTP_201_CREATED, operation_id="createUser")
async def create_user(body: UserCreate, session: SessionDep, actor: AdminActor) -> UserAdminOut:
    email = body.email.strip().lower()
    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um usuário com esse e-mail")

    user = User(
        name=body.name.strip(),
        email=email,
        password_hash=hash_password(body.password),
        role=body.role,
        department=(body.department or "").strip() or None,
        is_vip=body.is_vip,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Já existe um usuário com esse e-mail"
        ) from error
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="user.create",
            entity_type="user",
            entity_id=str(user.id),
            after=_snapshot(user),
        )
    )
    await session.commit()
    return UserAdminOut.model_validate(user)


@router.post("/invite", status_code=status.HTTP_201_CREATED, operation_id="inviteUser")
async def invite_user(
    body: UserInviteCreate, session: SessionDep, actor: AdminActor
) -> UserAdminOut:
    """Cria a conta sem senha utilizável e envia o link para a pessoa definir a dela."""
    email = body.email.strip().lower()
    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um usuário com esse e-mail")

    user = User(
        name=body.name.strip(),
        email=email,
        # Senha aleatória que ninguém conhece: a conta só abre depois que o link for usado.
        password_hash=hash_password(secrets.token_urlsafe(24) + "a1"),
        role=body.role,
        department=(body.department or "").strip() or None,
        is_vip=body.is_vip,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Já existe um usuário com esse e-mail"
        ) from error
    await create_invite(session, user)
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="user.invite",
            entity_type="user",
            entity_id=str(user.id),
            after=_snapshot(user),
        )
    )
    await session.commit()
    out = UserAdminOut.model_validate(user)
    out.invite_pending = True
    return out


@router.post(
    "/{user_id}/invite", status_code=status.HTTP_204_NO_CONTENT, operation_id="resendUserInvite"
)
async def resend_invite(user_id: uuid.UUID, session: SessionDep, actor: AdminActor) -> None:
    """Novo link para quem ainda não entrou ou esqueceu a senha. Os links anteriores caem."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    if not user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "A conta está desativada")
    await create_invite(session, user)
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="user.invite_resend",
            entity_type="user",
            entity_id=str(user.id),
        )
    )
    await session.commit()


@router.patch("/{user_id}", operation_id="updateUser")
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, session: SessionDep, actor: AdminActor
) -> UserAdminOut:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")

    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "department" in changes:
        changes["department"] = (changes["department"] or "").strip() or None

    # Quem administra não se tira do cargo nem se desativa: evita ficar sem nenhum administrador.
    if user.id == actor.id and (
        changes.get("role", user.role) is not Role.ADMIN
        or changes.get("is_active", user.is_active) is False
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Você não pode remover o próprio acesso de administrador nem desativar a própria conta",
        )

    before = _snapshot(user)
    for field, value in changes.items():
        setattr(user, field, value)
    after = _snapshot(user)
    if after != before:
        session.add(
            AuditLog(
                actor_id=actor.id,
                action="user.update",
                entity_type="user",
                entity_id=str(user.id),
                before=before,
                after=after,
            )
        )
    await session.commit()
    return UserAdminOut.model_validate(user)


@router.post(
    "/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT, operation_id="resetUserPassword"
)
async def reset_password(
    user_id: uuid.UUID, body: PasswordReset, session: SessionDep, actor: AdminActor
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    user.password_hash = hash_password(body.password)
    # A senha nunca vai para a auditoria: só o fato de que ela foi trocada.
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="user.password_reset",
            entity_type="user",
            entity_id=str(user.id),
        )
    )
    await session.commit()
