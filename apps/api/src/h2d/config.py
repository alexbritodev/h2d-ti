from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    environment: Literal["dev", "test", "production"] = "dev"
    database_url: str
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_ttl_minutes: int = Field(default=480, gt=0)
    cookie_secure: bool = True
    seed_password: SecretStr | None = None

    @model_validator(mode="after")
    def _production_is_safe(self) -> Self:
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE precisa ser verdadeiro em produção")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # os valores obrigatórios vêm do ambiente
