"""Ingestão de telemetria: persistência idempotente das séries temporais."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utc_now
from app.models.server import Server
from app.models.telemetry import AgentHeartbeat, DiskMetric, HostMetric, NetworkMetric
from app.schemas.agent import AgentMetricsRequest

# Janelas de aceitação do timestamp de coleta (proteção contra replay e relógio errado).
MAX_FUTURE_SKEW = timedelta(minutes=5)
MAX_AGE = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    recorded: bool
    duplicate: bool
    disks_recorded: int
    networks_recorded: int

    @property
    def accepted(self) -> bool:
        return self.recorded


class StaleMetricError(Exception):
    """Coleta antiga demais para ser confiável."""


class FutureMetricError(Exception):
    """Coleta com timestamp no futuro além da tolerância."""


def normalize_utc(value: datetime) -> datetime:
    """Converte para UTC naive, formato usado nas colunas DATETIME do MySQL."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def validate_collected_at(collected_at: datetime, *, now: datetime | None = None) -> datetime:
    moment = now or utc_now()
    normalized = normalize_utc(collected_at)
    if normalized > moment + MAX_FUTURE_SKEW:
        raise FutureMetricError()
    if normalized < moment - MAX_AGE:
        raise StaleMetricError()
    return normalized


def ingest_metrics(
    db: Session,
    *,
    server: Server,
    payload: AgentMetricsRequest,
    collected_at: datetime,
    now: datetime | None = None,
) -> IngestOutcome:
    """Grava a coleta. Repetir a mesma coleta não gera duplicidade (idempotência)."""
    moment = now or utc_now()

    already_recorded = db.scalar(
        select(HostMetric.id).where(
            HostMetric.server_id == server.id,
            HostMetric.collected_at == collected_at,
        )
    )
    if already_recorded is not None:
        return IngestOutcome(
            recorded=False, duplicate=True, disks_recorded=0, networks_recorded=0
        )

    host = payload.host
    db.add(
        HostMetric(
            server_id=server.id,
            collected_at=collected_at,
            received_at=moment,
            cpu_percent=host.cpu_percent,
            cpu_cores=host.cpu_cores,
            load_1=host.load_1,
            load_5=host.load_5,
            load_15=host.load_15,
            ram_total_bytes=host.ram_total_bytes,
            ram_used_bytes=host.ram_used_bytes,
            ram_available_bytes=host.ram_available_bytes,
            ram_percent=host.ram_percent,
            swap_total_bytes=host.swap_total_bytes,
            swap_used_bytes=host.swap_used_bytes,
            swap_percent=host.swap_percent,
            uptime_seconds=host.uptime_seconds,
            process_count=host.process_count,
            agent_version=payload.agent_version,
        )
    )

    for disk in payload.disks:
        db.add(
            DiskMetric(
                server_id=server.id,
                collected_at=collected_at,
                mount_point=disk.mount_point,
                filesystem=disk.filesystem,
                total_bytes=disk.total_bytes,
                used_bytes=disk.used_bytes,
                free_bytes=disk.free_bytes,
                used_percent=disk.used_percent,
            )
        )

    for network in payload.networks:
        db.add(
            NetworkMetric(
                server_id=server.id,
                collected_at=collected_at,
                interface=network.interface,
                rx_bytes=network.rx_bytes,
                tx_bytes=network.tx_bytes,
                rx_rate_bps=network.rx_rate_bps,
                tx_rate_bps=network.tx_rate_bps,
            )
        )

    server.last_metrics_at = moment
    server.agent_version = payload.agent_version
    db.flush()

    return IngestOutcome(
        recorded=True,
        duplicate=False,
        disks_recorded=len(payload.disks),
        networks_recorded=len(payload.networks),
    )


def record_heartbeat(
    db: Session,
    *,
    server: Server,
    agent_version: str,
    uptime_seconds: int,
    now: datetime | None = None,
) -> AgentHeartbeat:
    beat = AgentHeartbeat(
        server_id=server.id,
        received_at=now or utc_now(),
        agent_version=agent_version,
        uptime_seconds=uptime_seconds,
    )
    db.add(beat)
    return beat
