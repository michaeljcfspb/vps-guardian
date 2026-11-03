"""Consultas de leitura do painel: resumo, séries temporais e heartbeats."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.enums import ServerStatus
from app.core.security import utc_now
from app.models.server import Server
from app.models.telemetry import AgentHeartbeat, DiskMetric, HostMetric, NetworkMetric
from app.schemas.dashboard import (
    AverageMetrics,
    DashboardSummaryRead,
    HeartbeatRead,
    IncidentCounts,
    LatestTelemetryRead,
    MetricPoint,
    MetricsSeriesRead,
    ServerCounts,
)

# Janela -> (duração, passo do bucket). Passo escolhido para no máximo ~170 pontos.
WINDOWS: dict[str, tuple[timedelta, int]] = {
    "1h": (timedelta(hours=1), 60),
    "6h": (timedelta(hours=6), 180),
    "24h": (timedelta(hours=24), 900),
    "7d": (timedelta(days=7), 3600),
}

# Só considera "atual" a coleta desta janela ao calcular médias do dashboard.
FRESH_WINDOW = timedelta(minutes=5)


def _counts(db: Session) -> ServerCounts:
    rows = db.execute(select(Server.status, func.count()).group_by(Server.status)).all()
    by_status = {status: int(count) for status, count in rows}
    return ServerCounts(
        total=sum(by_status.values()),
        online=by_status.get(ServerStatus.ONLINE.value, 0),
        attention=by_status.get(ServerStatus.ATTENTION.value, 0),
        offline=by_status.get(ServerStatus.OFFLINE.value, 0),
        paused=by_status.get(ServerStatus.PAUSED.value, 0),
        unprovisioned=by_status.get(ServerStatus.UNPROVISIONED.value, 0),
        disabled=by_status.get(ServerStatus.DISABLED.value, 0),
    )


def _latest_collections(db: Session, since: datetime):
    return (
        select(
            HostMetric.server_id.label("server_id"),
            func.max(HostMetric.collected_at).label("collected_at"),
        )
        .where(HostMetric.collected_at >= since)
        .group_by(HostMetric.server_id)
        .subquery()
    )


def _averages(db: Session, *, now: datetime) -> AverageMetrics:
    since = now - FRESH_WINDOW
    latest = _latest_collections(db, since)

    host_rows = db.execute(
        select(HostMetric.cpu_percent, HostMetric.ram_percent).join(
            latest,
            and_(
                HostMetric.server_id == latest.c.server_id,
                HostMetric.collected_at == latest.c.collected_at,
            ),
        )
    ).all()

    if not host_rows:
        return AverageMetrics()

    cpu_values = [float(row[0]) for row in host_rows]
    ram_values = [float(row[1]) for row in host_rows]

    # Disco: pior ponto de montagem de cada servidor na última coleta.
    disk_rows = db.execute(
        select(DiskMetric.server_id, func.max(DiskMetric.used_percent))
        .join(
            latest,
            and_(
                DiskMetric.server_id == latest.c.server_id,
                DiskMetric.collected_at == latest.c.collected_at,
            ),
        )
        .group_by(DiskMetric.server_id)
    ).all()

    disk_values = [float(row[1]) for row in disk_rows if row[1] is not None]

    return AverageMetrics(
        cpu_percent=round(sum(cpu_values) / len(cpu_values), 2),
        ram_percent=round(sum(ram_values) / len(ram_values), 2),
        disk_percent=round(sum(disk_values) / len(disk_values), 2) if disk_values else None,
        servers_considered=len(host_rows),
    )


def dashboard_summary(db: Session, *, now: datetime | None = None) -> DashboardSummaryRead:
    moment = now or utc_now()
    last_heartbeat = db.scalar(select(func.max(Server.last_heartbeat_at)))
    age = int((moment - last_heartbeat).total_seconds()) if last_heartbeat else None

    return DashboardSummaryRead(
        servers=_counts(db),
        averages=_averages(db, now=moment),
        incidents=IncidentCounts(available=False),
        last_heartbeat_at=last_heartbeat,
        data_age_seconds=max(age, 0) if age is not None else None,
        generated_at=moment,
    )


def metrics_series(
    db: Session,
    *,
    server_id: str,
    window: str,
    now: datetime | None = None,
) -> MetricsSeriesRead:
    """Série agregada em buckets fixos — uma consulta por tipo de métrica."""
    moment = now or utc_now()
    span, step = WINDOWS[window]
    since = moment - span
    base = since

    def bucket(column):  # noqa: ANN001, ANN202 - expressão SQL reutilizada
        return func.floor((func.unix_timestamp(column) - func.unix_timestamp(base)) / step)

    host_rows = db.execute(
        select(
            bucket(HostMetric.collected_at).label("bucket"),
            func.min(HostMetric.collected_at).label("at"),
            func.avg(HostMetric.cpu_percent).label("cpu"),
            func.avg(HostMetric.ram_percent).label("ram"),
            func.avg(HostMetric.swap_percent).label("swap"),
        )
        .where(HostMetric.server_id == server_id, HostMetric.collected_at >= since)
        .group_by("bucket")
        .order_by("bucket")
    ).all()

    disk_rows = db.execute(
        select(
            bucket(DiskMetric.collected_at).label("bucket"),
            func.max(DiskMetric.used_percent).label("disk"),
        )
        .where(DiskMetric.server_id == server_id, DiskMetric.collected_at >= since)
        .group_by("bucket")
    ).all()

    net_rows = db.execute(
        select(
            bucket(NetworkMetric.collected_at).label("bucket"),
            func.avg(NetworkMetric.rx_rate_bps).label("rx"),
            func.avg(NetworkMetric.tx_rate_bps).label("tx"),
        )
        .where(NetworkMetric.server_id == server_id, NetworkMetric.collected_at >= since)
        .group_by("bucket")
    ).all()

    disks = {int(row.bucket): float(row.disk) for row in disk_rows if row.disk is not None}
    networks = {
        int(row.bucket): (
            float(row.rx) if row.rx is not None else None,
            float(row.tx) if row.tx is not None else None,
        )
        for row in net_rows
    }

    points = [
        MetricPoint(
            at=row.at,
            cpu_percent=round(float(row.cpu), 2) if row.cpu is not None else None,
            ram_percent=round(float(row.ram), 2) if row.ram is not None else None,
            swap_percent=round(float(row.swap), 2) if row.swap is not None else None,
            disk_percent=round(disks[int(row.bucket)], 2)
            if int(row.bucket) in disks
            else None,
            net_rx_bps=round(networks[int(row.bucket)][0], 2)
            if int(row.bucket) in networks and networks[int(row.bucket)][0] is not None
            else None,
            net_tx_bps=round(networks[int(row.bucket)][1], 2)
            if int(row.bucket) in networks and networks[int(row.bucket)][1] is not None
            else None,
        )
        for row in host_rows
    ]

    return MetricsSeriesRead(
        server_id=server_id,
        window=window,  # type: ignore[arg-type]
        step_seconds=step,
        from_at=since,
        to_at=moment,
        points=points,
    )


def recent_heartbeats(
    db: Session, *, server_id: str, limit: int = 100
) -> list[HeartbeatRead]:
    rows = db.scalars(
        select(AgentHeartbeat)
        .where(AgentHeartbeat.server_id == server_id)
        .order_by(AgentHeartbeat.received_at.desc(), AgentHeartbeat.id.desc())
        .limit(limit)
    ).all()
    return [
        HeartbeatRead(
            received_at=row.received_at,
            agent_version=row.agent_version,
            uptime_seconds=row.uptime_seconds,
        )
        for row in rows
    ]


def latest_telemetry(db: Session) -> list[LatestTelemetryRead]:
    """Última coleta de cada servidor, com pior disco e taxa de rede do momento.

    Uma consulta por tipo de métrica; serve a tabela do dashboard sem precisar de
    ``N+1`` requisições por servidor.
    """
    latest = (
        select(
            HostMetric.server_id.label("server_id"),
            func.max(HostMetric.collected_at).label("collected_at"),
        )
        .group_by(HostMetric.server_id)
        .subquery()
    )

    host_rows = db.execute(
        select(
            HostMetric.server_id,
            HostMetric.collected_at,
            HostMetric.cpu_percent,
            HostMetric.ram_percent,
            HostMetric.swap_percent,
            HostMetric.uptime_seconds,
        ).join(
            latest,
            and_(
                HostMetric.server_id == latest.c.server_id,
                HostMetric.collected_at == latest.c.collected_at,
            ),
        )
    ).all()

    if not host_rows:
        return []

    disk_rows = db.execute(
        select(DiskMetric.server_id, func.max(DiskMetric.used_percent))
        .join(
            latest,
            and_(
                DiskMetric.server_id == latest.c.server_id,
                DiskMetric.collected_at == latest.c.collected_at,
            ),
        )
        .group_by(DiskMetric.server_id)
    ).all()
    disks = {row[0]: float(row[1]) for row in disk_rows if row[1] is not None}

    net_rows = db.execute(
        select(
            NetworkMetric.server_id,
            func.sum(NetworkMetric.rx_rate_bps),
            func.sum(NetworkMetric.tx_rate_bps),
        )
        .join(
            latest,
            and_(
                NetworkMetric.server_id == latest.c.server_id,
                NetworkMetric.collected_at == latest.c.collected_at,
            ),
        )
        .group_by(NetworkMetric.server_id)
    ).all()
    networks = {
        row[0]: (
            float(row[1]) if row[1] is not None else None,
            float(row[2]) if row[2] is not None else None,
        )
        for row in net_rows
    }

    items: list[LatestTelemetryRead] = []
    for row in host_rows:
        rx, tx = networks.get(row.server_id, (None, None))
        items.append(
            LatestTelemetryRead(
                server_id=row.server_id,
                collected_at=row.collected_at,
                cpu_percent=round(float(row.cpu_percent), 2),
                ram_percent=round(float(row.ram_percent), 2),
                swap_percent=round(float(row.swap_percent), 2),
                disk_percent=round(disks[row.server_id], 2)
                if row.server_id in disks
                else None,
                net_rx_bps=round(rx, 2) if rx is not None else None,
                net_tx_bps=round(tx, 2) if tx is not None else None,
                uptime_seconds=int(row.uptime_seconds),
            )
        )

    items.sort(key=lambda item: item.server_id)
    return items
