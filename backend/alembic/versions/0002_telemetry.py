"""Telemetria: heartbeat, métricas de host, disco e rede.

Revision ID: 0002_telemetry
Revises: 0001_initial
Create Date: 2026-11-03

Índices compostos ``(server_id, collected_at)`` conforme PRD §8.3 para consultas
históricas. ``host_metrics`` tem chave única por coleta para ingestão idempotente.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_telemetry"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_KWARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}

FK_SERVER = "fk_%s_server_id_servers"


def upgrade() -> None:
    op.create_table(
        "agent_heartbeats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("uptime_seconds", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_agent_heartbeats"),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_agent_heartbeats_server_id_servers",
            ondelete="CASCADE",
        ),
        **TABLE_KWARGS,
    )
    op.create_index(
        "ix_agent_heartbeats_server_id_received_at",
        "agent_heartbeats",
        ["server_id", "received_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_heartbeats_received_at",
        "agent_heartbeats",
        ["received_at"],
        unique=False,
    )

    op.create_table(
        "host_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("cpu_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=False),
        sa.Column("load_1", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("load_5", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("load_15", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("ram_total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("ram_used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("ram_available_bytes", sa.BigInteger(), nullable=False),
        sa.Column("ram_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("swap_total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("swap_used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("swap_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("uptime_seconds", sa.BigInteger(), nullable=False),
        sa.Column("process_count", sa.Integer(), nullable=True),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_host_metrics"),
        sa.UniqueConstraint(
            "server_id",
            "collected_at",
            name="uq_host_metrics_server_id_collected_at",
        ),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_host_metrics_server_id_servers",
            ondelete="CASCADE",
        ),
        **TABLE_KWARGS,
    )
    op.create_index(
        "ix_host_metrics_collected_at", "host_metrics", ["collected_at"], unique=False
    )

    op.create_table(
        "disk_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("mount_point", sa.String(length=255), nullable=False),
        sa.Column("filesystem", sa.String(length=64), nullable=True),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("free_bytes", sa.BigInteger(), nullable=False),
        sa.Column("used_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_disk_metrics"),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_disk_metrics_server_id_servers",
            ondelete="CASCADE",
        ),
        **TABLE_KWARGS,
    )
    op.create_index(
        "ix_disk_metrics_server_id_collected_at",
        "disk_metrics",
        ["server_id", "collected_at"],
        unique=False,
    )

    op.create_table(
        "network_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("interface", sa.String(length=32), nullable=False),
        sa.Column("rx_bytes", sa.BigInteger(), nullable=False),
        sa.Column("tx_bytes", sa.BigInteger(), nullable=False),
        sa.Column("rx_rate_bps", sa.BigInteger(), nullable=True),
        sa.Column("tx_rate_bps", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_network_metrics"),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_network_metrics_server_id_servers",
            ondelete="CASCADE",
        ),
        **TABLE_KWARGS,
    )
    op.create_index(
        "ix_network_metrics_server_id_collected_at",
        "network_metrics",
        ["server_id", "collected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("network_metrics")
    op.drop_table("disk_metrics")
    op.drop_table("host_metrics")
    op.drop_table("agent_heartbeats")
