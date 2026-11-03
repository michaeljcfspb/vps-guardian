"""Rotas de autenticação do painel (PRD §10, §11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    CSRF_COOKIE_NAME,
    AppSettings,
    CurrentSession,
    CurrentUser,
    DbSession,
    client_ip,
    enforce_login_rate_limit,
    require_csrf,
    user_agent,
)
from app.core.enums import ActorType, AuditAction
from app.core.errors import RateLimitedError, UnauthorizedError
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse, UserRead
from app.services import auth as auth_service
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(
    response: Response, settings: AppSettings, *, token: str, csrf_token: str
) -> None:
    max_age = settings.session_ttl_minutes * 60
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )
    # Cookie CSRF: legível pelo painel para o double-submit (não é um segredo de sessão).
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_session_cookies(response: Response, settings: AppSettings) -> None:
    for name in (settings.session_cookie_name, CSRF_COOKIE_NAME):
        response.delete_cookie(
            key=name, path="/", domain=settings.cookie_domain, samesite=settings.cookie_samesite
        )


@router.post("/login", response_model=LoginResponse, summary="Autenticar no painel")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> LoginResponse:
    ip = client_ip(request, settings)
    agent = user_agent(request)

    try:
        enforce_login_rate_limit(request, settings, payload.email)
    except RateLimitedError:
        record_audit(
            db,
            action=AuditAction.LOGIN_RATE_LIMITED,
            actor_type=ActorType.USER,
            entity_type="user",
            ip_address=ip,
            user_agent=agent,
            details={"email": payload.email},
        )
        db.commit()
        raise

    user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    if user is None:
        record_audit(
            db,
            action=AuditAction.LOGIN_FAILURE,
            actor_type=ActorType.USER,
            entity_type="user",
            ip_address=ip,
            user_agent=agent,
            details={"email": payload.email, "reason": "invalid_credentials"},
        )
        db.commit()
        raise UnauthorizedError("Credenciais inválidas")

    _session, token, csrf_token = auth_service.create_session(
        db, user=user, ip_address=ip, user_agent=agent, settings=settings
    )
    record_audit(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        actor_type=ActorType.USER,
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        ip_address=ip,
        user_agent=agent,
    )
    db.commit()
    _set_session_cookies(response, settings, token=token, csrf_token=csrf_token)
    return LoginResponse(user=UserRead.model_validate(user))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Encerrar a sessão atual",
    dependencies=[Depends(require_csrf)],
)
def logout(
    response: Response,
    db: DbSession,
    settings: AppSettings,
    session: CurrentSession,
    user: CurrentUser,
) -> Response:
    auth_service.revoke_session(db, session=session, reason="logout")
    record_audit(
        db,
        action=AuditAction.LOGOUT,
        actor_type=ActorType.USER,
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    _clear_session_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse, summary="Dados da sessão atual")
def me(session: CurrentSession, user: CurrentUser) -> MeResponse:
    return MeResponse(
        user=UserRead.model_validate(user),
        session_expires_at=auth_service.session_expiry(session),
    )
