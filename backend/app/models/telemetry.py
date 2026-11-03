"""Séries temporais de telemetria (PRD §4.2, §4.3, §4.5).

Convenções:
- ``collected_at`` é o instante da coleta *no host*, em UTC (naive), enviado pelo agente;
- ``received_at`` é o instante de recebimento na central, sempre do servidor;
- a diferença entre os dois é a latência de transporte e é auditável.

``host_metrics`` tem restrição única em ``(server_id, collected_at)`` para tornar a
ingestão **idempotente**: reenvio após timeout não duplica a série.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utc_now
from app.db.base import Base


class HostMetric(Base):
    __tablename__ = "host_metrics"
    __table_args__ = (
        UniqueConstraint(
            "server_id", "collected_at", name="uq_host_metrics_server_id_collected_at"
        ),
        Index("ix_host_metrics_collected_at", "collected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )

    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    cpu_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    load_1: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    load_5: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    load_15: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)

    ram_total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ram_used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ram_available_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ram_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    swap_total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    swap_used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    swap_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    uptime_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False)
    process_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)


class DiskMetric(Base):
    __tablename__ = "disk_metrics"
    __table_args__ = (
        Index("ix_disk_metrics_server_id_collected_at", "server_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    mount_point: Mapped[str] = mapped_column(String(255), nullable=False)
    filesystem: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    free_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class NetworkMetric(Base):
    __tablename__ = "network_metrics"
    __table_args__ = (
        Index("ix_network_metrics_server_id_collected_at", "server_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    interface: Mapped[str] = mapped_column(String(32), nullable=False)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Taxa calculada entre coletas; nula na primeira leitura após reinício.
    rx_rate_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tx_rate_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class AgentHeartbeat(Base):
    """Histórico de heartbeat (PRD §4.5 / §7.3)."""

    __tablename__ = "agent_heartbeats"
    __table_args__ = (
        Index("ix_agent_heartbeats_server_id_received_at", "server_id", "received_at"),
        Index("ix_agent_heartbeats_received_at", "received_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    uptime_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False)


__all__ = [
    "AgentHeartbeat",
    "DiskMetric",
    "HostMetric",
    "NetworkMetric",
]
