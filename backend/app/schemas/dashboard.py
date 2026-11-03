"""Schemas do dashboard e das séries temporais (PRD §7.2, §7.3)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel, UtcDatetime

MetricsWindow = Literal["1h", "6h", "24h", "7d"]


class ServerCounts(ApiModel):
    total: int = 0
    online: int = 0
    attention: int = 0
    offline: int = 0
    paused: int = 0
    unprovisioned: int = 0
    disabled: int = 0


class AverageMetrics(ApiModel):
    """Médias calculadas sobre a **última coleta** de cada servidor."""

    cpu_percent: float | None = None
    ram_percent: float | None = None
    disk_percent: float | None = None
    servers_considered: int = 0


class IncidentCounts(ApiModel):
    """Fase 9 ainda não implementada: contadores sempre zerados e sinalizados."""

    open: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    available: bool = False


class DashboardSummaryRead(ApiModel):
    servers: ServerCounts
    averages: AverageMetrics
    incidents: IncidentCounts
    last_heartbeat_at: UtcDatetime | None = None
    data_age_seconds: int | None = None
    generated_at: UtcDatetime


class MetricPoint(ApiModel):
    at: UtcDatetime
    cpu_percent: float | None = None
    ram_percent: float | None = None
    swap_percent: float | None = None
    disk_percent: float | None = None
    net_rx_bps: float | None = None
    net_tx_bps: float | None = None


class MetricsSeriesRead(ApiModel):
    server_id: str
    window: MetricsWindow
    step_seconds: int
    from_at: UtcDatetime
    to_at: UtcDatetime
    points: list[MetricPoint] = Field(default_factory=list)


class HeartbeatRead(ApiModel):
    received_at: UtcDatetime
    agent_version: str
    uptime_seconds: int


class LatestTelemetryRead(ApiModel):
    """Última coleta conhecida de cada servidor (usada na tabela do dashboard)."""

    server_id: str
    collected_at: UtcDatetime
    cpu_percent: float | None = None
    ram_percent: float | None = None
    swap_percent: float | None = None
    disk_percent: float | None = None
    net_rx_bps: float | None = None
    net_tx_bps: float | None = None
    uptime_seconds: int | None = None
