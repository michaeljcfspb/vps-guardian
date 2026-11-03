"""Tipos e utilitários compartilhados entre schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

T = TypeVar("T")


def _to_utc_z(value: datetime) -> str:
    """Serializa sempre como UTC com sufixo ``Z`` (banco guarda naive UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_to_utc_z, return_type=str)]


class ApiModel(BaseModel):
    """Base dos schemas: rejeita campos desconhecidos (validação estrita)."""

    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class Page(ApiModel, Generic[T]):  # noqa: UP046 - genérico explícito exigido pelo Pydantic
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    schema_revision: str | None = None
    version: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
