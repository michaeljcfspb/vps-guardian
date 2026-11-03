"""Resumo agregado para o dashboard (PRD §7.2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.dashboard import DashboardSummaryRead
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryRead, summary="Indicadores gerais")
def summary(db: DbSession, _user: CurrentUser) -> DashboardSummaryRead:
    return dashboard_service.dashboard_summary(db)
