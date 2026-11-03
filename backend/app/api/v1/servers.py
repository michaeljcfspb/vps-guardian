"""Rotas de servidores e credenciais de agente (PRD §4.1, §10).

Todas exigem sessão de administrador (exceto leitura, liberada para operadores) e
proteção CSRF, aplicada pelo router.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import (
    AppSettings,
    CurrentAdmin,
    CurrentUser,
    DbSession,
    client_ip,
    require_csrf,
    user_agent,
)
from app.core.enums import ServerEnvironment, ServerPanel, ServerStatus
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.credential import ServerCredential
from app.models.server import Server
from app.schemas.common import Page
from app.schemas.server import (
    CredentialRead,
    ProvisioningTokenRead,
    RotateCredentialRead,
    ServerCreate,
    ServerRead,
    ServerUpdate,
)
from app.services import provisioning as provisioning_service
from app.services import servers as server_service

router = APIRouter(
    prefix="/servers", tags=["servers"], dependencies=[Depends(require_csrf)]
)


def _to_read(server: Server, active_credentials: int = 0) -> ServerRead:
    model = ServerRead.model_validate(server)
    return model.model_copy(update={"active_credentials": active_credentials})


def _get_or_404(db: DbSession, server_id: str) -> Server:
    server = server_service.get_server(db, server_id)
    if server is None:
        raise NotFoundError("Servidor não encontrado")
    return server


def _register_url(settings: AppSettings) -> str:
    path = f"{settings.api_prefix}/agent/register"
    if settings.public_base_url:
        return f"{settings.public_base_url.rstrip('/')}{path}"
    return path


@router.get("", response_model=Page[ServerRead], summary="Listar servidores")
def list_servers(
    db: DbSession,
    _user: CurrentUser,
    status_filter: Annotated[ServerStatus | None, Query(alias="status")] = None,
    panel: Annotated[ServerPanel | None, Query()] = None,
    environment: Annotated[ServerEnvironment | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ServerRead]:
    stmt = server_service.server_query(
        status=status_filter, panel=panel, environment=environment, search=search
    )
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.limit(limit).offset(offset)).all())
    counts = server_service.active_credential_counts(db, [row.id for row in rows])
    items = [_to_read(row, counts.get(row.id, 0)) for row in rows]
    return Page[ServerRead](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=ServerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar servidor",
)
def create_server(
    payload: ServerCreate,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
    settings: AppSettings,
) -> ServerRead:
    try:
        server = server_service.create_server(
            db,
            payload=payload,
            actor_user_id=admin.id,
            ip_address=client_ip(request, settings),
            user_agent=user_agent(request),
        )
    except server_service.ConflictNameError as exc:
        raise ConflictError(str(exc)) from exc
    db.commit()
    return _to_read(server)


@router.get("/{server_id}", response_model=ServerRead, summary="Detalhar servidor")
def get_server(server_id: str, db: DbSession, _user: CurrentUser) -> ServerRead:
    server = _get_or_404(db, server_id)
    counts = server_service.active_credential_counts(db, [server.id])
    return _to_read(server, counts.get(server.id, 0))


@router.patch("/{server_id}", response_model=ServerRead, summary="Atualizar servidor")
def update_server(
    server_id: str,
    payload: ServerUpdate,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
    settings: AppSettings,
) -> ServerRead:
    server = _get_or_404(db, server_id)
    try:
        server = server_service.update_server(
            db,
            server=server,
            payload=payload,
            actor_user_id=admin.id,
            ip_address=client_ip(request, settings),
            user_agent=user_agent(request),
        )
    except server_service.ConflictNameError as exc:
        raise ConflictError(str(exc)) from exc
    except server_service.InvalidIntervalError as exc:
        raise BadRequestError(
            "heartbeat_timeout_seconds deve ser pelo menos 2x collection_interval_seconds"
        ) from exc
    db.commit()
    counts = server_service.active_credential_counts(db, [server.id])
    return _to_read(server, counts.get(server.id, 0))


@router.post(
    "/{server_id}/provisioning-token",
    response_model=ProvisioningTokenRead,
    summary="Emitir token temporário de provisionamento",
)
def issue_provisioning_token(
    server_id: str,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
    settings: AppSettings,
) -> ProvisioningTokenRead:
    server = _get_or_404(db, server_id)
    if server.status == ServerStatus.DISABLED.value:
        raise BadRequestError("Servidor desativado não pode ser provisionado")

    token, row = provisioning_service.issue_provisioning_token(
        db,
        server=server,
        actor_user_id=admin.id,
        ttl_minutes=settings.provisioning_token_ttl_minutes,
        ip_address=client_ip(request, settings),
        user_agent=user_agent(request),
    )
    db.commit()
    return ProvisioningTokenRead(
        server_id=server.id,
        token=token,
        token_prefix=row.token_prefix,
        expires_at=row.expires_at,
        register_url=_register_url(settings),
    )


@router.get(
    "/{server_id}/credentials",
    response_model=list[CredentialRead],
    summary="Listar credenciais do servidor (sem segredos)",
)
def list_credentials(
    server_id: str, db: DbSession, _user: CurrentUser
) -> list[CredentialRead]:
    _get_or_404(db, server_id)
    rows = db.scalars(
        select(ServerCredential)
        .where(ServerCredential.server_id == server_id)
        .order_by(ServerCredential.created_at.desc())
    ).all()
    return [CredentialRead.model_validate(row) for row in rows]


@router.post(
    "/{server_id}/rotate-credential",
    response_model=RotateCredentialRead,
    summary="Rotacionar credencial do agente",
)
def rotate_credential(
    server_id: str,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
    settings: AppSettings,
) -> RotateCredentialRead:
    server = _get_or_404(db, server_id)
    token, prefix, expires_at, revoked = provisioning_service.rotate_credential(
        db,
        server=server,
        actor_user_id=admin.id,
        ttl_days=settings.agent_credential_ttl_days,
        ip_address=client_ip(request, settings),
        user_agent=user_agent(request),
    )
    db.commit()
    return RotateCredentialRead(
        server_id=server.id,
        credential=token,
        token_prefix=prefix,
        expires_at=expires_at,
        revoked_previous=revoked,
    )


@router.post(
    "/{server_id}/credentials/revoke",
    summary="Revogar todas as credenciais ativas",
)
def revoke_credentials(
    server_id: str,
    request: Request,
    db: DbSession,
    admin: CurrentAdmin,
    settings: AppSettings,
) -> dict[str, int]:
    server = _get_or_404(db, server_id)
    revoked = provisioning_service.revoke_credentials(
        db,
        server=server,
        actor_user_id=admin.id,
        ip_address=client_ip(request, settings),
        user_agent=user_agent(request),
    )
    db.commit()
    return {"revoked": revoked}


@router.post("/{server_id}/pause", response_model=ServerRead, summary="Pausar monitoramento")
def pause_server(
    server_id: str, request: Request, db: DbSession, admin: CurrentAdmin, settings: AppSettings
) -> ServerRead:
    server = _get_or_404(db, server_id)
    server_service.set_operational_status(
        db,
        server=server,
        status=ServerStatus.PAUSED,
        actor_user_id=admin.id,
        ip_address=client_ip(request, settings),
        user_agent=user_agent(request),
    )
    db.commit()
    return _to_read(server)


@router.post("/{server_id}/resume", response_model=ServerRead, summary="Retomar monitoramento")
def resume_server(
    server_id: str, request: Request, db: DbSession, admin: CurrentAdmin, settings: AppSettings
) -> ServerRead:
    server = _get_or_404(db, server_id)
    target = (
        ServerStatus.UNPROVISIONED if server.registered_at is None else ServerStatus.OFFLINE
    )
    server_service.set_operational_status(
        db,
        server=server,
        status=target,
        actor_user_id=admin.id,
        reason="monitoramento retomado; aguardando heartbeat",
        ip_address=client_ip(request, settings),
        user_agent=user_agent(request),
    )
    db.commit()
    return _to_read(server)


@router.post("/{server_id}/disable", response_model=ServerRead, summary="Desativar servidor")
def disable_server(
    server_id: str, request: Request, db: DbSession, admin: CurrentAdmin, settings: AppSettings
) -> ServerRead:
    server = _get_or_404(db, server_id)
    server_service.set_operational_status(
        db,
        server=server,
        status=ServerStatus.DISABLED,
        actor_user_id=admin.id,
        reason="servidor desativado pelo administrador",
        ip_address=client_ip(request, settings),
        user_agent=user_agent(request),
    )
    db.commit()
    return _to_read(server)
