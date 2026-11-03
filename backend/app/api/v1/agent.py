"""Rotas do agente (PRD §10).

Autenticação por credencial individual (Bearer) sobre HTTPS. Nenhuma rota aqui aceita
cookie de sessão, e nenhuma delas executa comandos.
"""

from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, Request, status

from app.api.deps import (
    AgentRateLimited,
    AppSettings,
    CurrentAgent,
    DbSession,
    check_rate_limit,
    client_ip,
)
from app.core.enums import ActorType, AuditAction
from app.core.errors import BadRequestError, ForbiddenError, UnauthorizedError
from app.core.security import utc_now
from app.schemas.agent import (
    AgentConfigResponse,
    AgentFeatures,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentMetricsRequest,
    AgentMetricsResponse,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
)
from app.services import provisioning as provisioning_service
from app.services import servers as server_service
from app.services import telemetry as telemetry_service
from app.services.audit import record_audit

router = APIRouter(prefix="/agent", tags=["agent"])

# Rejeita timestamps absurdos (relógio quebrado); desvios menores são apenas reportados.
_MAX_SKEW_SECONDS = 86400
_REGISTER_MAX_PER_MINUTE = 10


@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trocar token de provisionamento por credencial individual",
)
def register(
    payload: AgentRegistrationRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> AgentRegistrationResponse:
    ip = client_ip(request, settings)
    check_rate_limit(
        "agent_register",
        f"ip:{ip or 'unknown'}",
        max_events=_REGISTER_MAX_PER_MINUTE,
        window_seconds=60,
    )

    try:
        server, credential, prefix, expires_at, _revoked = provisioning_service.register_agent(
            db, payload=payload, ip_address=ip
        )
    except provisioning_service.InvalidProvisioningTokenError as exc:
        record_audit(
            db,
            action=AuditAction.AGENT_AUTH_FAILURE,
            actor_type=ActorType.AGENT,
            entity_type="provisioning_token",
            ip_address=ip,
            details={"reason": "invalid_or_expired_token"},
        )
        db.commit()
        raise UnauthorizedError("Token de provisionamento inválido ou expirado") from exc
    except provisioning_service.DescriptionRequiredError as exc:
        raise ForbiddenError("Servidor pausado ou desativado") from exc

    db.commit()
    return AgentRegistrationResponse(
        server_id=server.id,
        server_name=server.name,
        credential=credential,
        token_prefix=prefix,
        collection_interval_seconds=server.collection_interval_seconds,
        heartbeat_timeout_seconds=server.heartbeat_timeout_seconds,
        credential_expires_at=expires_at,
    )


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
    summary="Registrar heartbeat do agente",
)
def heartbeat(
    payload: AgentHeartbeatRequest,
    ctx: CurrentAgent,
    db: DbSession,
    _rate: AgentRateLimited,
) -> AgentHeartbeatResponse:
    now = utc_now()
    sent_at = payload.sent_at.astimezone(UTC).replace(tzinfo=None)
    skew = int((now - sent_at).total_seconds())
    if abs(skew) > _MAX_SKEW_SECONDS:
        raise BadRequestError(
            "Timestamp do agente fora da tolerância; verifique o relógio do host",
            details={"max_skew_seconds": _MAX_SKEW_SECONDS},
        )

    server = server_service.apply_heartbeat(
        db, server=ctx.server, agent_version=payload.agent_version, now=now
    )
    telemetry_service.record_heartbeat(
        db,
        server=server,
        agent_version=payload.agent_version,
        uptime_seconds=payload.uptime_seconds,
        now=now,
    )
    db.commit()

    return AgentHeartbeatResponse(
        server_id=server.id,
        status=server.status,
        collection_interval_seconds=server.collection_interval_seconds,
        received_at=now,
    )


@router.post(
    "/metrics",
    response_model=AgentMetricsResponse,
    summary="Receber uma coleta de métricas do host",
)
def ingest_metrics(
    payload: AgentMetricsRequest,
    ctx: CurrentAgent,
    db: DbSession,
    _rate: AgentRateLimited,
) -> AgentMetricsResponse:
    now = utc_now()
    try:
        collected_at = telemetry_service.validate_collected_at(payload.collected_at, now=now)
    except telemetry_service.FutureMetricError as exc:
        raise BadRequestError(
            "collected_at está no futuro além da tolerância",
            details={"max_future_skew_seconds": 300},
        ) from exc
    except telemetry_service.StaleMetricError as exc:
        raise BadRequestError(
            "collected_at é antigo demais para ser armazenado",
            details={"max_age_hours": 24},
        ) from exc

    outcome = telemetry_service.ingest_metrics(
        db,
        server=ctx.server,
        payload=payload,
        collected_at=collected_at,
        now=now,
    )
    db.commit()

    return AgentMetricsResponse(
        server_id=ctx.server.id,
        collected_at=collected_at,
        recorded=outcome.recorded,
        duplicate=outcome.duplicate,
        disks_recorded=outcome.disks_recorded,
        networks_recorded=outcome.networks_recorded,
        received_at=now,
    )


@router.get(
    "/config",
    response_model=AgentConfigResponse,
    summary="Configuração vigente para o agente",
)
def get_config(ctx: CurrentAgent) -> AgentConfigResponse:
    server = ctx.server
    return AgentConfigResponse(
        server_id=server.id,
        server_name=server.name,
        collection_interval_seconds=server.collection_interval_seconds,
        heartbeat_timeout_seconds=server.heartbeat_timeout_seconds,
        features=AgentFeatures(metrics=True, docker=False, checks=False),
    )
