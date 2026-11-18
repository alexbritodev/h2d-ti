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
    # Modelo de linguagem (OpenRouter). O padrão é um modelo gratuito; a lista de reserva entra
    # quando o primeiro estiver indisponível ou no limite. Modelos mudam: confira em openrouter.ai.
    openrouter_model: str = "openrouter/free"
    openrouter_fallback_models: str = ""
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    # Teto de chamadas ao modelo por dia, somando todos os usuários. Modelo gratuito no
    # OpenRouter: 50/dia (1000 com US$ 10 em créditos). Padrão 200 evita bloqueio local prematuro.
    llm_daily_request_limit: int = Field(default=200, ge=0)
    # Limites do chat por conversa.
    chat_max_user_messages: int = Field(default=30, gt=0)
    chat_max_message_chars: int = Field(default=2000, gt=0)
    # Pausa entre pedaços da resposta enviada em SSE (a resposta já vem pronta do modelo).
    chat_stream_delay_seconds: float = Field(default=0.02, ge=0)
    # Configuração dos Agentes do Chat
    guardiao_enabled: bool = True
    guardiao_model: str = ""
    guardiao_fast_only: bool = False
    validador_enabled: bool = True
    validador_model: str = ""
    validador_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    # n8n (rede interna do Docker). Sem URL e segredo, os eventos ficam na fila e nada é enviado.
    n8n_webhook_url: str = ""
    # Segredo compartilhado do HMAC, nos dois sentidos (API para n8n e n8n para API).
    n8n_hmac_secret: SecretStr | None = None
    # Validade do link de convite (primeiro acesso ou nova senha). O mínimo pedido foi 24 h.
    invite_ttl_hours: int = Field(default=48, ge=24)
    # O seed cria usuários com uma senha única e conhecida. Em produção só roda se for
    # pedido de forma explícita, e só serve para demonstração com dados fictícios.
    allow_demo_seed: bool = False
    # Escritório virtual (experimento). Desligado, nada é registrado nem exposto.
    escritorio_virtual_enabled: bool = False
    # Libera os cenários roteirizados da tela (não grava nada no banco).
    escritorio_virtual_demo: bool = False

    @model_validator(mode="after")
    def _production_is_safe(self) -> Self:
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE precisa ser verdadeiro em produção")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # os valores obrigatórios vêm do ambiente
