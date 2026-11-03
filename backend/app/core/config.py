"""Configuração central da aplicação, carregada exclusivamente de variáveis de ambiente.

Nenhum segredo possui valor padrão. A ausência de ``GUARDIAN_SECRET_KEY`` ou de
``GUARDIAN_DATABASE_URL`` impede a inicialização (fail-fast), conforme PRD §11.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import quote_plus, urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "staging", "production", "test"]

_FORBIDDEN_DB_SCHEMES = ("sqlite", "postgres", "postgresql", "mysql+asyncpg")


def _split_csv(value: Any) -> Any:
    """Aceita lista JSON ou string separada por vírgulas vinda do ambiente."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Configuração imutável por processo."""

    model_config = SettingsConfigDict(
        env_prefix="GUARDIAN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )

    # --- Aplicação ---------------------------------------------------------
    app_env: AppEnv = "development"
    app_name: str = "VPS Guardian"
    deployment_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = True
    # URL pública da API (ex.: https://guardian.exemplo.com), usada para montar
    # instruções de provisionamento exibidas ao administrador.
    public_base_url: str | None = None

    # --- Segurança ---------------------------------------------------------
    secret_key: SecretStr = Field(min_length=32)
    session_ttl_minutes: int = Field(default=720, ge=5, le=10080)
    session_idle_timeout_minutes: int = Field(default=120, ge=5, le=2880)
    cookie_secure: bool | None = None
    cookie_domain: str | None = None
    cookie_samesite: Literal["strict", "lax"] = "strict"
    cors_origins: list[str] = Field(default_factory=list)
    # Proxies reversos confiáveis (ex.: IP do Traefik no Easypanel). Só quando o par
    # TCP pertence a esta lista o header X-Forwarded-For é considerado.
    trusted_proxy_ips: list[str] = Field(default_factory=list)

    # --- Banco de dados ----------------------------------------------------
    # Duas formas equivalentes de configurar a conexão:
    #   a) GUARDIAN_DATABASE_URL (URL completa, senha precisa de URL-encoding);
    #   b) GUARDIAN_DB_HOST/PORT/NAME/USER/PASSWORD (a URL é montada com escaping
    #      automático — caminho recomendado, evita erro com @ # / na senha).
    database_url: str | None = None
    db_host: str | None = None
    db_port: int = Field(default=3306, ge=1, le=65535)
    db_name: str | None = None
    db_user: str | None = None
    db_password: SecretStr | None = None

    # Automação de instalação: esperar o MySQL e aplicar migrations ao iniciar.
    auto_migrate: bool = True
    db_wait_timeout_seconds: int = Field(default=180, ge=10, le=1800)

    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60)
    db_echo: bool = False
    db_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # --- Rate limiting -----------------------------------------------------
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_window_seconds: int = Field(default=300, ge=10, le=86400)
    agent_max_requests_per_minute: int = Field(default=20, ge=2, le=600)

    # --- Provisionamento de agentes ---------------------------------------
    provisioning_token_ttl_minutes: int = Field(default=15, ge=1, le=1440)
    agent_credential_ttl_days: int = Field(default=0, ge=0, le=3650)

    # --- Banco de testes ---------------------------------------------------
    test_database_url: str | None = None

    # --- Derivados ---------------------------------------------------------
    @field_validator("secret_key")
    @classmethod
    def _reject_weak_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 32:
            raise ValueError("GUARDIAN_SECRET_KEY deve ter ao menos 32 caracteres")
        if raw.lower() in {"change-me", "changeme", "secret", "password"}:
            raise ValueError("GUARDIAN_SECRET_KEY é um valor previsível e foi rejeitado")
        return value

    @field_validator("database_url")
    @classmethod
    def _require_mysql(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        value = value.strip()
        scheme = urlsplit(value).scheme.lower()
        if not scheme:
            raise ValueError("GUARDIAN_DATABASE_URL deve ser uma URL de conexão válida")
        if any(scheme.startswith(bad) for bad in _FORBIDDEN_DB_SCHEMES):
            raise ValueError(
                "Apenas MySQL é permitido (PRD §17.2.4). "
                f"Esquema recusado: {scheme}"
            )
        if not scheme.startswith("mysql"):
            raise ValueError(f"Esquema de banco não suportado: {scheme}")
        return value

    @field_validator("db_name", "db_user")
    @classmethod
    def _safe_identifier(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", value):
            raise ValueError("nome de banco/usuário deve conter apenas letras, números e _")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("trusted_proxy_ips", mode="before")
    @classmethod
    def _split_proxies(cls, value: Any) -> Any:
        return _split_csv(value)

    @field_validator("cors_origins")
    @classmethod
    def _validate_origins(cls, value: list[str]) -> list[str]:
        for origin in value:
            if origin == "*":
                raise ValueError("CORS curinga não é permitido (PRD §11)")
            if not re.match(r"^https?://[^/\s]+$", origin):
                raise ValueError(f"Origem CORS inválida (sem path/barra final): {origin}")
        return value

    @model_validator(mode="after")
    def _resolve_database_url(self) -> Settings:
        """Monta a URL a partir das partes quando ``GUARDIAN_DATABASE_URL`` não existe.

        Isso elimina a necessidade de URL-encoding manual na senha do MySQL — fonte
        comum de falha de instalação quando a senha contém ``@``, ``#``, ``/`` ou ``:``.
        """
        if self.database_url:
            return self

        parts = (
            ("GUARDIAN_DB_HOST", self.db_host),
            ("GUARDIAN_DB_NAME", self.db_name),
            ("GUARDIAN_DB_USER", self.db_user),
            ("GUARDIAN_DB_PASSWORD", self.db_password),
        )
        missing = [name for name, value in parts if not value]
        if missing:
            raise ValueError(
                "Defina GUARDIAN_DATABASE_URL ou então: " + ", ".join(missing)
            )

        password = self.db_password.get_secret_value() if self.db_password else ""
        url = (
            f"mysql+pymysql://{quote_plus(self.db_user or '')}:{quote_plus(password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        object.__setattr__(self, "database_url", url)
        return self

    @model_validator(mode="after")
    def _check_idle_below_ttl(self) -> Settings:
        if self.session_idle_timeout_minutes > self.session_ttl_minutes:
            raise ValueError(
                "GUARDIAN_SESSION_IDLE_TIMEOUT_MINUTES não pode exceder "
                "GUARDIAN_SESSION_TTL_MINUTES"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def secure_cookies(self) -> bool:
        """Em produção o cookie é sempre ``Secure``; fora dela, configurável."""
        if self.is_production:
            return True
        return bool(self.cookie_secure)

    @property
    def docs_enabled(self) -> bool:
        """Swagger/OpenAPI expostos apenas fora de produção (PRD §10)."""
        return not self.is_production

    @property
    def effective_database_url(self) -> str:
        if self.is_test and self.test_database_url:
            return self.test_database_url
        if self.database_url is None:  # pragma: no cover - garantido pelo validator
            raise RuntimeError("database_url não configurada")
        return self.database_url

    def __repr__(self) -> str:  # nunca expor o segredo em logs/tracebacks
        host = urlsplit(self.database_url).hostname if self.database_url else None
        return (
            f"Settings(app_env={self.app_env!r}, deployment_version={self.deployment_version!r}, "
            f"database_host={host!r})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Usado apenas em testes para recarregar o ambiente."""
    get_settings.cache_clear()
