"""Inventário de servidores VPS monitorados (PRD §4.1)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ServerEnvironment, ServerPanel, ServerStatus
from app.core.security import new_id, utc_now
from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.credential import ProvisioningToken, ServerCredential


class Server(Base):
    __tablename__ = "servers"
    __table_args__ = (
        Index("ix_servers_status_last_heartbeat_at", "status", "last_heartbeat_at"),
        Index("ix_servers_panel", "panel"),
        Index("ix_servers_environment", "environment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    environment: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ServerEnvironment.OTHER.value
    )
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    panel: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ServerPanel.NONE.value
    )

    os_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kernel: Mapped[str | None] = mapped_column(String(80), nullable=True)
    architecture: Mapped[str | None] = mapped_column(String(32), nullable=True)

    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    collection_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    heartbeat_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ServerStatus.UNPROVISIONED.value
    )
    status_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_metrics_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now, onupdate=utc_now
    )

    credentials: Mapped[list[ServerCredential]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    provisioning_tokens: Mapped[list[ProvisioningToken]] = relationship(
        back_populates="server",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def accepts_telemetry(self) -> bool:
        """Servidor pausado ou desativado não deve receber telemetria."""
        return self.status not in {ServerStatus.PAUSED.value, ServerStatus.DISABLED.value}
