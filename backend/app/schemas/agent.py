"""Schemas das rotas de agente (PRD §10).

O agente usa autenticação própria (Bearer) — nunca a sessão do painel.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import ApiModel, UtcDatetime

_AGENT_VERSION_RE = r"^[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.]+)?$"


class AgentRegistrationRequest(ApiModel):
    """Troca do token de provisionamento pela credencial individual."""

    provisioning_token: str = Field(min_length=32, max_length=128)
    agent_version: str = Field(pattern=_AGENT_VERSION_RE, max_length=32)
    hostname: str | None = Field(default=None, max_length=255)
    os_name: str | None = Field(default=None, max_length=80)
    os_version: str | None = Field(default=None, max_length=40)
    kernel: str | None = Field(default=None, max_length=80)
    architecture: str | None = Field(default=None, max_length=32)

    @field_validator("provisioning_token")
    @classmethod
    def _no_whitespace(cls, value: str) -> str:
        token = value.strip()
        if any(char.isspace() for char in token):
            raise ValueError("token inválido")
        return token


class AgentRegistrationResponse(ApiModel):
    """A credencial em claro aparece **somente** nesta resposta."""

    server_id: str
    server_name: str
    credential: str
    token_prefix: str
    collection_interval_seconds: int
    heartbeat_timeout_seconds: int
    credential_expires_at: UtcDatetime | None


class AgentHeartbeatRequest(ApiModel):
    sent_at: datetime
    agent_version: str = Field(pattern=_AGENT_VERSION_RE, max_length=32)
    uptime_seconds: int = Field(ge=0)
    hostname: str | None = Field(default=None, max_length=255)

    @field_validator("sent_at")
    @classmethod
    def _require_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("sent_at deve conter fuso horário (UTC)")
        return value


class AgentHeartbeatResponse(ApiModel):
    server_id: str
    status: str
    collection_interval_seconds: int
    received_at: UtcDatetime


class AgentFeatures(ApiModel):
    metrics: bool = False
    docker: bool = False
    checks: bool = False


class AgentConfigResponse(ApiModel):
    server_id: str
    server_name: str
    collection_interval_seconds: int
    heartbeat_timeout_seconds: int
    features: AgentFeatures
    config_version: int = 1
