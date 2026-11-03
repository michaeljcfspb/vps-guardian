"""Registro central dos modelos — importar aqui garante metadata completa no Alembic."""

from app.db.base import Base
from app.models.audit import AuditLog, SystemSetting
from app.models.credential import ProvisioningToken, ServerCredential
from app.models.server import Server
from app.models.telemetry import AgentHeartbeat, DiskMetric, HostMetric, NetworkMetric
from app.models.user import User, UserSession

__all__ = [
    "AgentHeartbeat",
    "AuditLog",
    "Base",
    "DiskMetric",
    "HostMetric",
    "NetworkMetric",
    "ProvisioningToken",
    "Server",
    "ServerCredential",
    "SystemSetting",
    "User",
    "UserSession",
]
