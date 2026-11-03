"""Leitura de telemetria agregada (dashboard e consultas)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.dashboard import LatestTelemetryRead
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get(
    "/latest",
    response_model=list[LatestTelemetryRead],
    summary="Última coleta de cada servidor",
)
def latest(db: DbSession, _user: CurrentUser) -> list[LatestTelemetryRead]:
    return dashboard_service.latest_telemetry(db)
