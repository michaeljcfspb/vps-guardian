"""Rotas de sistema: informações da central e consulta de auditoria (PRD §11)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import AppSettings, CurrentAdmin, CurrentUser, DbSession, require_csrf
from app.models.server import Server
from app.schemas.common import Page
from app.schemas.system import AuditLogRead, SystemInfoRead
from app.services.audit import audit_query
from app.services.schema import current_schema_revision

router = APIRouter(
    prefix="/system", tags=["system"], dependencies=[Depends(require_csrf)]
)


@router.get("/info", response_model=SystemInfoRead, summary="Informações da instalação")
def info(db: DbSession, _user: CurrentUser, settings: AppSettings) -> SystemInfoRead:
    server_count = int(db.scalar(select(func.count()).select_from(Server)) or 0)
    return SystemInfoRead(
        name=settings.app_name,
        version=settings.deployment_version,
        environment=settings.app_env,
        api_prefix=settings.api_prefix,
        schema_revision=current_schema_revision(),
        server_count=server_count,
    )


@router.get(
    "/audit-logs",
    response_model=Page[AuditLogRead],
    summary="Consultar trilha de auditoria",
)
def list_audit_logs(
    db: DbSession,
    _admin: CurrentAdmin,
    action: Annotated[str | None, Query(max_length=100)] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditLogRead]:
    stmt = audit_query(action=action, entity_type=entity_type, entity_id=entity_id)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    return Page[AuditLogRead](
        items=[AuditLogRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
