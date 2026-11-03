"""Credenciais de agente e tokens de provisionamento (PRD §4.1, §9.3, §9.4).

Nenhum segredo é persistido em claro: guardamos ``sha256(token)`` e um prefixo
identificável — ver ADR-0004.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import new_id, utc_now
from app.db.base import Base
from app.models.server import Server


class ServerCredential(Base):
    """Credencial permanente e individual de um agente."""

    __tablename__ = "agent_credentials"
    __table_args__ = (
        Index("ix_agent_credentials_server_id_revoked_at", "server_id", "revoked_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="principal")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    server: Mapped[Server] = relationship(back_populates="credentials")

    def is_usable(self, now: datetime) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > now


class ProvisioningToken(Base):
    """Token temporário de uso único para registrar um agente."""

    __tablename__ = "provisioning_tokens"
    __table_args__ = (
        Index("ix_provisioning_tokens_server_id_used_at", "server_id", "used_at"),
        Index("ix_provisioning_tokens_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    server: Mapped[Server] = relationship(back_populates="provisioning_tokens")

    def is_usable(self, now: datetime) -> bool:
        return self.used_at is None and self.expires_at > now
