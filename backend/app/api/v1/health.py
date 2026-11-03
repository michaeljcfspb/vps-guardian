"""Health checks da central (PRD §17.6)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import AppSettings, DbSession
from app.db.session import ping_database
from app.schemas.common import HealthResponse, ReadinessResponse
from app.services.schema import current_schema_revision

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness")
def health(settings: AppSettings) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.deployment_version,
        environment=settings.app_env,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness (dependências externas)",
    responses={503: {"description": "Banco de dados indisponível"}},
)
def readiness(response: Response, settings: AppSettings, db: DbSession) -> ReadinessResponse:
    del db  # a verificação usa conexão dedicada e curta
    database_ok = ping_database()
    revision = current_schema_revision() if database_ok else None

    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if database_ok else "degraded",
        database="ok" if database_ok else "unavailable",
        schema_revision=revision,
        version=settings.deployment_version,
    )
