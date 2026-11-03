"""Registro central dos modelos — importar aqui garante metadata completa no Alembic."""

from app.db.base import Base
from app.models.audit import AuditLog, SystemSetting
from app.models.credential import ProvisioningToken, ServerCredential
from app.models.server import Server
from app.models.user import User, UserSession

__all__ = [
    "AuditLog",
    "Base",
    "ProvisioningToken",
    "Server",
    "ServerCredential",
    "SystemSetting",
    "User",
    "UserSession",
]
