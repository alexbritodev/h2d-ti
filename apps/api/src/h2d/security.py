import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from h2d.config import get_settings

_ALGORITHM = "HS256"
_hasher = PasswordHasher()


MIN_PASSWORD_LENGTH = 6


def check_password_policy(password: str) -> str:
    """Regra única de senha nova: 6 ou mais caracteres, com letras e números."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"A senha precisa ter ao menos {MIN_PASSWORD_LENGTH} caracteres")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("A senha precisa ter letras e números")
    return password


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash(uuid.uuid4().hex)


def burn_verification_time(password: str) -> None:
    """Gasta o mesmo tempo de uma senha real, para o tempo não revelar se o e-mail existe."""
    verify_password(_dummy_hash(), password)


def create_session_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=_ALGORITHM)


def read_session_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
