"""Enums de domínio persistidos como texto.

Optamos por colunas ``VARCHAR`` (e não ``ENUM`` nativo do MySQL) para que inclusões de
valores não exijam ``ALTER TABLE`` em produção. A validação é feita na camada Pydantic
e nos serviços. Ver ADR-0005.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"


class ServerStatus(StrEnum):
    """PRD §4.5 — estados propostos."""

    UNPROVISIONED = "unprovisioned"
    ONLINE = "online"
    ATTENTION = "attention"
    OFFLINE = "offline"
    PAUSED = "paused"
    DISABLED = "disabled"


class ServerEnvironment(StrEnum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    OTHER = "other"


class ServerPanel(StrEnum):
    EASYPANEL = "easypanel"
    PORTAINER = "portainer"
    ICP = "icp"
    NONE = "none"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ActorType(StrEnum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class AuditAction(StrEnum):
    """Ações registradas em ``audit_logs`` (PRD §11)."""

    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGIN_RATE_LIMITED = "auth.login.rate_limited"
    LOGOUT = "auth.logout"
    SERVER_CREATED = "server.created"
    SERVER_UPDATED = "server.updated"
    SERVER_PAUSED = "server.paused"
    SERVER_RESUMED = "server.resumed"
    SERVER_DISABLED = "server.disabled"
    PROVISIONING_TOKEN_ISSUED = "server.provisioning_token.issued"  # noqa: S105
    AGENT_REGISTERED = "agent.registered"
    AGENT_CREDENTIAL_ROTATED = "agent.credential.rotated"
    AGENT_CREDENTIAL_REVOKED = "agent.credential.revoked"
    AGENT_AUTH_FAILURE = "agent.auth.failure"


def is_valid_enum(enum_cls: type[StrEnum], value: str) -> bool:
    return value in {member.value for member in enum_cls}
