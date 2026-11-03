"""Estrutura inicial: usuários, sessões, servidores, credenciais e auditoria.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-03

Escrita à mão para ser determinística (não depende de banco acessível) e revisada
contra ``app/models``. Convenções: InnoDB, utf8mb4, datas em UTC, PK BIGINT para
séries/entidades internas e CHAR(36) para identificadores públicos.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_KWARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        **TABLE_KWARGS,
    )

    op.create_table(
        "servers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=80), nullable=True),
        sa.Column("panel", sa.String(length=16), nullable=False),
        sa.Column("os_name", sa.String(length=80), nullable=True),
        sa.Column("os_version", sa.String(length=40), nullable=True),
        sa.Column("kernel", sa.String(length=80), nullable=True),
        sa.Column("architecture", sa.String(length=32), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("collection_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("heartbeat_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_reason", sa.String(length=255), nullable=True),
        sa.Column("agent_version", sa.String(length=32), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("last_metrics_at", sa.DateTime(), nullable=True),
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_servers"),
        sa.UniqueConstraint("name", name="uq_servers_name"),
        **TABLE_KWARGS,
    )
    op.create_index("ix_servers_panel", "servers", ["panel"], unique=False)
    op.create_index("ix_servers_environment", "servers", ["environment"], unique=False)
    op.create_index(
        "ix_servers_status_last_heartbeat_at",
        "servers",
        ["status", "last_heartbeat_at"],
        unique=False,
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_user_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        **TABLE_KWARGS,
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_user_sessions_user_id_revoked_at",
        "user_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)

    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=120), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_agent_credentials"),
        sa.UniqueConstraint("token_hash", name="uq_agent_credentials_token_hash"),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_agent_credentials_server_id_servers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_agent_credentials_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        **TABLE_KWARGS,
    )
    op.create_index(
        "ix_agent_credentials_server_id", "agent_credentials", ["server_id"], unique=False
    )
    op.create_index(
        "ix_agent_credentials_server_id_revoked_at",
        "agent_credentials",
        ["server_id", "revoked_at"],
        unique=False,
    )

    op.create_table(
        "provisioning_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_by_ip", sa.String(length=45), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_provisioning_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_provisioning_tokens_token_hash"),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["servers.id"],
            name="fk_provisioning_tokens_server_id_servers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_provisioning_tokens_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        **TABLE_KWARGS,
    )
    op.create_index(
        "ix_provisioning_tokens_server_id", "provisioning_tokens", ["server_id"], unique=False
    )
    op.create_index(
        "ix_provisioning_tokens_server_id_used_at",
        "provisioning_tokens",
        ["server_id", "used_at"],
        unique=False,
    )
    op.create_index(
        "ix_provisioning_tokens_expires_at", "provisioning_tokens", ["expires_at"], unique=False
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        **TABLE_KWARGS,
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index(
        "ix_audit_logs_entity_type_entity_id",
        "audit_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("key", name="pk_system_settings"),
        **TABLE_KWARGS,
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("audit_logs")
    op.drop_table("provisioning_tokens")
    op.drop_table("agent_credentials")
    op.drop_table("user_sessions")
    op.drop_table("servers")
    op.drop_table("users")
