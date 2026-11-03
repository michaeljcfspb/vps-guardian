"""Schemas das rotas de agente (PRD §10).

O agente usa autenticação própria (Bearer) — nunca a sessão do painel.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiModel, UtcDatetime

_AGENT_VERSION_RE = r"^[0-9]+\.[0-9]+\.[0-9]+([-+][A-Za-z0-9.]+)?$"
_INTERFACE_RE = re.compile(r"^[A-Za-z0-9_.:@-]{1,32}$")
_MAX_DISKS = 64
_MAX_INTERFACES = 32
_MAX_BYTES = 2**63 - 1


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


class HostMetricIn(ApiModel):
    cpu_percent: float = Field(ge=0, le=100)
    cpu_cores: int = Field(ge=1, le=4096)
    load_1: float = Field(ge=0, le=100000)
    load_5: float = Field(ge=0, le=100000)
    load_15: float = Field(ge=0, le=100000)
    ram_total_bytes: int = Field(ge=0, le=_MAX_BYTES)
    ram_used_bytes: int = Field(ge=0, le=_MAX_BYTES)
    ram_available_bytes: int = Field(ge=0, le=_MAX_BYTES)
    ram_percent: float = Field(ge=0, le=100)
    swap_total_bytes: int = Field(ge=0, le=_MAX_BYTES)
    swap_used_bytes: int = Field(ge=0, le=_MAX_BYTES)
    swap_percent: float = Field(ge=0, le=100)
    uptime_seconds: int = Field(ge=0, le=10**12)
    process_count: int | None = Field(default=None, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def _memory_is_consistent(self) -> Self:
        if self.ram_used_bytes > self.ram_total_bytes:
            raise ValueError("ram_used_bytes não pode exceder ram_total_bytes")
        if self.ram_available_bytes > self.ram_total_bytes:
            raise ValueError("ram_available_bytes não pode exceder ram_total_bytes")
        if self.swap_used_bytes > self.swap_total_bytes:
            raise ValueError("swap_used_bytes não pode exceder swap_total_bytes")
        return self


class DiskMetricIn(ApiModel):
    mount_point: str = Field(min_length=1, max_length=255)
    filesystem: str | None = Field(default=None, max_length=64)
    total_bytes: int = Field(ge=0, le=_MAX_BYTES)
    used_bytes: int = Field(ge=0, le=_MAX_BYTES)
    free_bytes: int = Field(ge=0, le=_MAX_BYTES)
    used_percent: float = Field(ge=0, le=100)

    @field_validator("mount_point")
    @classmethod
    def _no_control_chars(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("mount_point contém caracteres de controle")
        return value

    @model_validator(mode="after")
    def _disk_is_consistent(self) -> Self:
        if self.used_bytes > self.total_bytes:
            raise ValueError("used_bytes não pode exceder total_bytes")
        if self.free_bytes > self.total_bytes:
            raise ValueError("free_bytes não pode exceder total_bytes")
        return self


class NetworkMetricIn(ApiModel):
    interface: str = Field(min_length=1, max_length=32)
    rx_bytes: int = Field(ge=0, le=_MAX_BYTES)
    tx_bytes: int = Field(ge=0, le=_MAX_BYTES)
    rx_rate_bps: int | None = Field(default=None, ge=0, le=_MAX_BYTES)
    tx_rate_bps: int | None = Field(default=None, ge=0, le=_MAX_BYTES)

    @field_validator("interface")
    @classmethod
    def _valid_interface(cls, value: str) -> str:
        if not _INTERFACE_RE.match(value):
            raise ValueError("nome de interface inválido")
        return value


class AgentMetricsRequest(ApiModel):
    """Payload de uma coleta completa (PRD §4.2)."""

    collected_at: datetime
    agent_version: str = Field(pattern=_AGENT_VERSION_RE, max_length=32)
    host: HostMetricIn
    disks: list[DiskMetricIn] = Field(default_factory=list, max_length=_MAX_DISKS)
    networks: list[NetworkMetricIn] = Field(default_factory=list, max_length=_MAX_INTERFACES)

    @field_validator("collected_at")
    @classmethod
    def _require_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("collected_at deve conter fuso horário (UTC)")
        return value


class AgentMetricsResponse(ApiModel):
    server_id: str
    collected_at: UtcDatetime
    recorded: bool
    duplicate: bool
    disks_recorded: int
    networks_recorded: int
    received_at: UtcDatetime


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
