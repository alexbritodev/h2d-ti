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
    # Chave do OpenRouter (embeddings e modelo de linguagem, F2/F3). Opcional até o código usá-la.
    openrouter_api_key: SecretStr | None = None
    # Arquivos originais enviados na ingestão (volume compartilhado entre API e worker).
    upload_dir: str = "/data/uploads"
    # Cache do modelo de embeddings (ADR-003). Na imagem de produção o modelo já vem baixado.
    fastembed_cache_dir: str = "/models"
    # O seed cria usuários com uma senha única e conhecida. Em produção só roda se for
    # pedido de forma explícita, e só serve para demonstração com dados fictícios.
    allow_demo_seed: bool = False

    @model_validator(mode="after")
    def _production_is_safe(self) -> Self:
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE precisa ser verdadeiro em produção")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # os valores obrigatórios vêm do ambiente
