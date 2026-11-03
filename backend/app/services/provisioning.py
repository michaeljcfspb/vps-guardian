"""Provisionamento de agentes: token temporário → credencial permanente (PRD §9.3).

Garantias implementadas:
- token de provisionamento é de **uso único** e expira (TTL padrão 15 min);
- ao registrar, credenciais antigas do servidor são revogadas (sem duplicidade);
- a credencial em claro aparece apenas na resposta que a emite (ADR-0004).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import ActorType, AuditAction
from app.core.security import generate_token, hash_token, token_prefix, utc_now
from app.models.credential import ProvisioningToken, ServerCredential
from app.models.server import Server
from app.schemas.agent import AgentRegistrationRequest
from app.services.audit import record_audit


class InvalidProvisioningTokenError(Exception):
    """Token inexistente, expirado ou já utilizado."""


class DescriptionRequiredError(Exception):
    """O servidor não aceita provisionamento no estado atual."""


def _create_credential(
    db: Session,
    *,
    server: Server,
    actor_user_id: int | None,
    ttl_days: int,
    now: datetime,
    label: str = "principal",
) -> tuple[str, ServerCredential]:
    token = generate_token()
    expires_at = now + timedelta(days=ttl_days) if ttl_days > 0 else None
    credential = ServerCredential(
        server_id=server.id,
        token_hash=hash_token(token),
        token_prefix=token_prefix(token),
        label=label[:80],
        created_at=now,
        expires_at=expires_at,
        created_by_user_id=actor_user_id,
    )
    db.add(credential)
    db.flush()
    return token, credential


def issue_provisioning_token(
    db: Session,
    *,
    server: Server,
    actor_user_id: int,
    ttl_minutes: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> tuple[str, ProvisioningToken]:
    """Emite um novo token e invalida os anteriores não utilizados."""
    moment = now or utc_now()

    # Só pode existir um token de provisionamento ativo por servidor.
    db.execute(
        delete(ProvisioningToken).where(
            ProvisioningToken.server_id == server.id,
            ProvisioningToken.used_at.is_(None),
        )
    )

    token = generate_token()
    row = ProvisioningToken(
        server_id=server.id,
        token_hash=hash_token(token),
        token_prefix=token_prefix(token),
        created_at=moment,
        expires_at=moment + timedelta(minutes=ttl_minutes),
        created_by_user_id=actor_user_id,
    )
    db.add(row)
    db.flush()

    record_audit(
        db,
        action=AuditAction.PROVISIONING_TOKEN_ISSUED,
        actor_type=ActorType.USER,
        actor_id=actor_user_id,
        entity_type="server",
        entity_id=server.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"token_prefix": row.token_prefix, "expires_at": row.expires_at.isoformat()},
    )
    return token, row


def register_agent(
    db: Session,
    *,
    payload: AgentRegistrationRequest,
    ip_address: str | None = None,
    now: datetime | None = None,
) -> tuple[Server, str, str, datetime | None, int]:
    """Consome o token de provisionamento e cria a credencial permanente.

    Retorna ``(servidor, credencial_em_claro, prefixo, expiração, revogadas)``.
    """
    moment = now or utc_now()
    row = db.scalar(
        select(ProvisioningToken)
        .where(ProvisioningToken.token_hash == hash_token(payload.provisioning_token))
        .with_for_update()
    )
    if row is None or not row.is_usable(moment):
        raise InvalidProvisioningTokenError()

    server = db.get(Server, row.server_id)
    if server is None:
        raise InvalidProvisioningTokenError()
    if not server.accepts_telemetry():
        raise DescriptionRequiredError()

    row.used_at = moment
    row.used_by_ip = ip_address

    revoked = _revoke_active_credentials(
        db, server=server, reason="novo registro do agente", now=moment
    )

    token, credential = _create_credential(
        db, server=server, actor_user_id=None, ttl_days=0, now=moment, label="registro"
    )

    # Metadados informados pelo próprio agente (não sobrescrevem o que o admin definiu
    # como nome/painel; apenas dados de sistema, que o agente conhece melhor).
    if payload.hostname:
        server.hostname = payload.hostname.lower()
    if payload.os_name:
        server.os_name = payload.os_name
    if payload.os_version:
        server.os_version = payload.os_version
    if payload.kernel:
        server.kernel = payload.kernel
    if payload.architecture:
        server.architecture = payload.architecture
    if server.registered_at is None:
        server.registered_at = moment
    server.agent_version = payload.agent_version
    server.status_reason = "aguardando primeiro heartbeat"

    record_audit(
        db,
        action=AuditAction.AGENT_REGISTERED,
        actor_type=ActorType.AGENT,
        actor_id=server.id,
        entity_type="server",
        entity_id=server.id,
        ip_address=ip_address,
        details={
            "agent_version": payload.agent_version,
            "token_prefix": row.token_prefix,
            "revoked_credentials": revoked,
            "credential_prefix": credential.token_prefix,
        },
    )
    return server, token, credential.token_prefix, credential.expires_at, revoked


def rotate_credential(
    db: Session,
    *,
    server: Server,
    actor_user_id: int,
    ttl_days: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str, datetime | None, int]:
    """Revoga as credenciais ativas e emite uma nova (rotação atômica)."""
    moment = now or utc_now()
    revoked = _revoke_active_credentials(
        db, server=server, reason="rotação de credencial", now=moment
    )
    try:
        token, credential = _create_credential(
            db,
            server=server,
            actor_user_id=actor_user_id,
            ttl_days=ttl_days,
            now=moment,
            label="rotação",
        )
    except IntegrityError as exc:  # pragma: no cover - colisão de hash é improvável
        db.rollback()
        raise RuntimeError("falha ao gerar credencial; tente novamente") from exc

    record_audit(
        db,
        action=AuditAction.AGENT_CREDENTIAL_ROTATED,
        actor_type=ActorType.USER,
        actor_id=actor_user_id,
        entity_type="server",
        entity_id=server.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={
            "credential_prefix": credential.token_prefix,
            "revoked": revoked,
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        },
    )
    return token, credential.token_prefix, credential.expires_at, revoked


def revoke_credentials(
    db: Session,
    *,
    server: Server,
    actor_user_id: int,
    reason: str = "revogação manual",
    ip_address: str | None = None,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> int:
    moment = now or utc_now()
    revoked = _revoke_active_credentials(db, server=server, reason=reason, now=moment)
    record_audit(
        db,
        action=AuditAction.AGENT_CREDENTIAL_REVOKED,
        actor_type=ActorType.USER,
        actor_id=actor_user_id,
        entity_type="server",
        entity_id=server.id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"revoked": revoked, "reason": reason},
    )
    return revoked


def _revoke_active_credentials(
    db: Session, *, server: Server, reason: str, now: datetime
) -> int:
    active = db.scalars(
        select(ServerCredential).where(
            ServerCredential.server_id == server.id,
            ServerCredential.revoked_at.is_(None),
        )
    ).all()
    for credential in active:
        credential.revoked_at = now
        credential.revoked_reason = reason[:120]
    return len(active)
