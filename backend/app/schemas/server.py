"""Schemas de servidores e provisionamento (PRD §4.1)."""

from __future__ import annotations

import ipaddress
import re
from typing import Self

from pydantic import Field, field_validator, model_validator

from app.core.enums import ServerEnvironment, ServerPanel, ServerStatus
from app.schemas.common import ApiModel, UtcDatetime

_HOSTNAME_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)
_NAME_RE = re.compile(r"^[\w][\w .:/()+-]*$", re.UNICODE)
_MAX_TAGS = 20
_MAX_TAG_LENGTH = 32


def check_name(value: str) -> str:
    if not _NAME_RE.match(value):
        raise ValueError("nome contém caracteres não permitidos")
    return value


def check_hostname(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower()
    if not _HOSTNAME_RE.match(value):
        raise ValueError("hostname inválido")
    return value


def check_ip(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as exc:
        raise ValueError("endereço IP inválido") from exc


def check_tags(value: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in value:
        tag = raw.strip()
        if not tag:
            continue
        if len(tag) > _MAX_TAG_LENGTH:
            raise ValueError(f"cada tag deve ter no máximo {_MAX_TAG_LENGTH} caracteres")
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tag)
    return cleaned


class ServerBase(ApiModel):
    name: str = Field(min_length=2, max_length=120)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    environment: ServerEnvironment = ServerEnvironment.OTHER
    provider: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=80)
    panel: ServerPanel = ServerPanel.NONE
    tags: list[str] = Field(default_factory=list, max_length=_MAX_TAGS)
    notes: str | None = Field(default=None, max_length=4000)
    collection_interval_seconds: int = Field(default=30, ge=15, le=3600)
    heartbeat_timeout_seconds: int = Field(default=90, ge=30, le=7200)

    @field_validator("name")
    @classmethod
    def _v_name(cls, value: str) -> str:
        return check_name(value)

    @field_validator("hostname")
    @classmethod
    def _v_hostname(cls, value: str | None) -> str | None:
        return check_hostname(value)

    @field_validator("ip_address")
    @classmethod
    def _v_ip(cls, value: str | None) -> str | None:
        return check_ip(value)

    @field_validator("tags")
    @classmethod
    def _v_tags(cls, value: list[str]) -> list[str]:
        return check_tags(value)

    @model_validator(mode="after")
    def _timeout_covers_two_intervals(self) -> Self:
        """Um heartbeat perdido precisa ser detectável: timeout >= 2 intervalos."""
        if self.heartbeat_timeout_seconds < 2 * self.collection_interval_seconds:
            raise ValueError(
                "heartbeat_timeout_seconds deve ser pelo menos 2x collection_interval_seconds"
            )
        return self


class ServerCreate(ServerBase):
    pass


class ServerUpdate(ApiModel):
    """Atualização parcial; apenas campos enviados são alterados."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    hostname: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=45)
    environment: ServerEnvironment | None = None
    provider: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=80)
    panel: ServerPanel | None = None
    tags: list[str] | None = Field(default=None, max_length=_MAX_TAGS)
    notes: str | None = Field(default=None, max_length=4000)
    collection_interval_seconds: int | None = Field(default=None, ge=15, le=3600)
    heartbeat_timeout_seconds: int | None = Field(default=None, ge=30, le=7200)

    @field_validator("name")
    @classmethod
    def _v_name(cls, value: str | None) -> str | None:
        return None if value is None else check_name(value)

    @field_validator("hostname")
    @classmethod
    def _v_hostname(cls, value: str | None) -> str | None:
        return check_hostname(value)

    @field_validator("ip_address")
    @classmethod
    def _v_ip(cls, value: str | None) -> str | None:
        return check_ip(value)

    @field_validator("tags")
    @classmethod
    def _v_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else check_tags(value)


class ServerRead(ApiModel):
    id: str
    name: str
    hostname: str | None
    ip_address: str | None
    environment: ServerEnvironment
    provider: str | None
    region: str | None
    panel: ServerPanel
    os_name: str | None
    os_version: str | None
    kernel: str | None
    architecture: str | None
    tags: list[str]
    notes: str | None
    collection_interval_seconds: int
    heartbeat_timeout_seconds: int
    status: ServerStatus
    status_reason: str | None
    agent_version: str | None
    last_heartbeat_at: UtcDatetime | None
    last_metrics_at: UtcDatetime | None
    registered_at: UtcDatetime | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
    active_credentials: int = 0


class ProvisioningTokenRead(ApiModel):
    """Token exibido uma única vez; inclui a URL de registro (ADR-0004)."""

    server_id: str
    token: str
    token_prefix: str
    expires_at: UtcDatetime
    register_url: str


class CredentialRead(ApiModel):
    id: str
    token_prefix: str
    label: str
    created_at: UtcDatetime
    expires_at: UtcDatetime | None
    revoked_at: UtcDatetime | None
    revoked_reason: str | None
    last_used_at: UtcDatetime | None


class RotateCredentialRead(ApiModel):
    server_id: str
    credential: str
    token_prefix: str
    expires_at: UtcDatetime | None
    revoked_previous: int
