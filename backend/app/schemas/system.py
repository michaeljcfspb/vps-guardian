"""Schemas de sistema (informações e auditoria)."""

from __future__ import annotations

from typing import Any

from app.schemas.common import ApiModel, UtcDatetime


class SystemInfoRead(ApiModel):
    name: str
    version: str
    environment: str
    api_prefix: str
    schema_revision: str | None
    server_count: int


class AuditLogRead(ApiModel):
    id: int
    action: str
    actor_type: str
    actor_id: str | None
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    details: dict[str, Any] | None
    created_at: UtcDatetime
