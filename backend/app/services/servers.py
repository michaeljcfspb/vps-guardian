"""Regras de negócio de servidores (PRD §4.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    ActorType,
    AuditAction,
    ServerEnvironment,
    ServerPanel,
    ServerStatus,
)
from app.core.security import utc_now
from app.models.credential import ServerCredential
from app.models.server import Server
from app.schemas.server import ServerCreate, ServerUpdate
from app.services.audit import record_audit


def get_server(db: Session, server_id: str) -> Server | None:
    return db.get(Server, server_id)


def get_server_by_name(db: Session, name: str) -> Server | None:
    return db.scalar(select(Server).where(Server.name == name))


def server_query(
    *,
    status: ServerStatus | None = None,
    panel: ServerPanel | None = None,
    environment: ServerEnvironment | None = None,
    search: str | None = None,
) -> Select[tuple[Server]]:
    stmt = select(Server).order_by(Server.name.asc())
    if status is not None:
        stmt = stmt.where(Server.status == status.value)
    if panel is not None:
        stmt = stmt.where(Server.panel == panel.value)
    if environment is not None:
        stmt = stmt.where(Server.environment == environment.value)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(Server.name.like(term) | Server.hostname.like(term))
    return stmt


def count_servers(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Server)) or 0)


def active_credential_counts(db: Session, server_ids: list[str]) -> dict[str, int]:
    """Contagem de credenciais utilizáveis por servidor, em uma única consulta."""
    if not server_ids:
        return {}
    now = utc_now()
    rows = db.execute(
        select(ServerCredential.server_id, func.count(ServerCredential.id))
        .where(
            ServerCredential.server_id.in_(server_ids),
            ServerCredential.revoked_at.is_(None),
            (ServerCredential.expires_at.is_(None)) | (ServerCredential.expires_at > now),
        )
        .group_by(ServerCredential.server_id)
    ).all()
    return {server_id: int(count) for server_id, count in rows}


def create_server(
    db: Session,
    *,
    payload: ServerCreate,
    actor_user_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Server:
    server = Server(
        name=payload.name,
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        environment=payload.environment.value,
        provider=payload.provider,
        region=payload.region,
        panel=payload.panel.value,
        tags=payload.tags,
        notes=payload.notes,
        collection_interval_seconds=payload.collection_interval_seconds,
        heartbeat_timeout_seconds=payload.heartbeat_timeout_seconds,
        status=ServerStatus.UNPROVISIONED.value,
    )
    db.add(server)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictNameError(payload.name) from exc

    record_audit(
        db,
        action=AuditAction.SERVER_CREATED,
        actor_type=ActorType.USER,
        actor_id=actor_user_id,
        entity_type="server",
        entity_id=server.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "name": server.name,
            "panel": server.panel,
            "environment": server.environment,
        },
    )
    return server


def update_server(
    db: Session,
    *,
    server: Server,
    payload: ServerUpdate,
    actor_user_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Server:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        return server

    mutable = {
        "name",
        "hostname",
        "ip_address",
        "environment",
        "provider",
        "region",
        "panel",
        "tags",
        "notes",
        "collection_interval_seconds",
        "heartbeat_timeout_seconds",
    }
    unknown = set(changes) - mutable
    if unknown:  # pragma: no cover - protegido pelo schema
        raise ValueError(f"campos não atualizáveis: {sorted(unknown)}")

    for field, value in changes.items():
        if field in {"environment", "panel"} and value is not None:
            value = value.value if hasattr(value, "value") else value
        setattr(server, field, value)

    # Revalida a invariante de timeout após a alteração parcial.
    if server.heartbeat_timeout_seconds < 2 * server.collection_interval_seconds:
        raise InvalidIntervalError()

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictNameError(changes.get("name", server.name)) from exc

    record_audit(
        db,
        action=AuditAction.SERVER_UPDATED,
        actor_type=ActorType.USER,
        actor_id=actor_user_id,
        entity_type="server",
        entity_id=server.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"fields": sorted(changes)},
    )
    return server


def set_operational_status(
    db: Session,
    *,
    server: Server,
    status: ServerStatus,
    actor_user_id: int,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Server:
    """Pausa, retoma ou desativa o monitoramento de um servidor."""
    mapping = {
        ServerStatus.PAUSED: AuditAction.SERVER_PAUSED,
        ServerStatus.DISABLED: AuditAction.SERVER_DISABLED,
        ServerStatus.UNPROVISIONED: AuditAction.SERVER_RESUMED,
    }
    previous = server.status
    server.status = status.value
    server.status_reason = reason
    record_audit(
        db,
        action=mapping.get(status, AuditAction.SERVER_UPDATED),
        actor_type=ActorType.USER,
        actor_id=actor_user_id,
        entity_type="server",
        entity_id=server.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"from": previous, "to": status.value, "reason": reason},
    )
    return server


def apply_heartbeat(
    db: Session,
    *,
    server: Server,
    agent_version: str,
    now: datetime | None = None,
) -> Server:
    """Atualiza o estado do servidor a partir de um heartbeat autenticado."""
    moment = now or utc_now()
    server.last_heartbeat_at = moment
    server.agent_version = agent_version
    if server.status in {ServerStatus.UNPROVISIONED.value, ServerStatus.OFFLINE.value,
                         ServerStatus.ATTENTION.value}:
        server.status = ServerStatus.ONLINE.value
        server.status_reason = None
    return server


class ConflictNameError(Exception):
    """Nome de servidor já utilizado."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Já existe um servidor com o nome {name!r}")


class InvalidIntervalError(Exception):
    """Timeout de heartbeat incompatível com o intervalo de coleta."""
