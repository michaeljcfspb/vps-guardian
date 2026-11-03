"""Registro de auditoria (PRD §11).

A auditoria é gravada na **mesma transação** da operação. Quem precisa auditar uma
falha (ex.: login inválido) deve commitar antes de levantar a exceção — caso contrário
o ``rollback`` do fim da requisição descarta o registro.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.enums import ActorType, AuditAction
from app.models.audit import AuditLog

_MAX_UA = 255


def record_audit(
    db: Session,
    *,
    action: AuditAction | str,
    actor_type: ActorType | str,
    actor_id: str | int | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Adiciona um evento de auditoria à sessão (sem commit)."""
    entry = AuditLog(
        action=str(action),
        actor_type=str(actor_type),
        actor_id=None if actor_id is None else str(actor_id),
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        ip_address=ip_address,
        user_agent=(user_agent or None) and user_agent[:_MAX_UA],
        details=details or None,
    )
    db.add(entry)
    return entry


def audit_query(
    *,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> Select[tuple[AuditLog]]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    return stmt


def count_audit(db: Session, *, action: str | None = None) -> int:
    stmt = select(func.count()).select_from(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return int(db.scalar(stmt) or 0)
