"""Dependências HTTP: sessão do painel, CSRF, agente e rate limiting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import UserRole
from app.core.errors import ForbiddenError, RateLimitedError, UnauthorizedError
from app.core.rate_limit import RateLimitRegistry
from app.core.security import hash_token, utc_now
from app.db.session import get_db
from app.models.credential import ServerCredential
from app.models.server import Server
from app.models.user import User, UserSession
from app.services.auth import csrf_matches, load_session

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_COOKIE_NAME = "guardian_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]

_limiters = RateLimitRegistry()


def reset_limiters() -> None:
    """Usado em testes para isolar janelas de rate limit."""
    _limiters.reset_all()


def client_ip(request: Request, settings: Settings) -> str | None:
    """IP do cliente, confiando em X-Forwarded-For apenas de proxies conhecidos."""
    peer = request.client.host if request.client else None
    if peer and settings.trusted_proxy_ips and peer in settings.trusted_proxy_ips:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()[:45] or peer
    return peer[:45] if peer else None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _resolve_session(
    request: Request, db: Session, settings: Settings
) -> tuple[UserSession, User]:
    cached = getattr(request.state, "auth", None)
    if cached is not None:
        return cached

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise UnauthorizedError("Sessão ausente")

    result = load_session(db, token=token, settings=settings)
    if result is None:
        raise UnauthorizedError("Sessão inválida ou expirada")

    request.state.auth = result
    return result


def get_current_session(request: Request, db: DbSession, settings: AppSettings) -> UserSession:
    session, _user = _resolve_session(request, db, settings)
    return session


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    _session, user = _resolve_session(request, db, settings)
    return user


def require_admin(request: Request, db: DbSession, settings: AppSettings) -> User:
    user = get_current_user(request, db, settings)
    if user.role != UserRole.ADMIN.value:
        raise ForbiddenError("Ação restrita a administradores")
    return user


def require_csrf(request: Request, db: DbSession, settings: AppSettings) -> None:
    """Proteção CSRF double-submit; ignorada em métodos seguros."""
    if request.method in SAFE_METHODS:
        return
    session, _user = _resolve_session(request, db, settings)
    if not csrf_matches(session, request.headers.get(CSRF_HEADER_NAME)):
        raise ForbiddenError("Token CSRF ausente ou inválido")


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(require_admin)]
CurrentSession = Annotated[UserSession, Depends(get_current_session)]
CsrfProtected = Annotated[None, Depends(require_csrf)]


@dataclass(frozen=True, slots=True)
class AgentContext:
    server: Server
    credential: ServerCredential


def get_current_agent(request: Request, db: DbSession, settings: AppSettings) -> AgentContext:
    """Autenticação própria do agente: Bearer token, nunca cookie de sessão."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("Credencial de agente ausente")

    credential = db.scalar(
        select(ServerCredential).where(ServerCredential.token_hash == hash_token(token))
    )
    if credential is None:
        raise UnauthorizedError("Credencial de agente inválida")

    now = utc_now()
    if not credential.is_usable(now):
        raise UnauthorizedError("Credencial de agente revogada ou expirada")

    server = db.get(Server, credential.server_id)
    if server is None:
        raise UnauthorizedError("Credencial de agente inválida")

    if not server.accepts_telemetry():
        raise ForbiddenError("Monitoramento do servidor está pausado ou desativado")

    credential.last_used_at = now
    return AgentContext(server=server, credential=credential)


CurrentAgent = Annotated[AgentContext, Depends(get_current_agent)]


def enforce_login_rate_limit(
    request: Request, settings: AppSettings, key: str
) -> None:
    """Aplica o limite de login por IP e por e-mail (ADR-0006)."""
    limiter = _limiters.register(
        "login",
        max_events=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
    )
    ip = client_ip(request, settings) or "unknown"
    for candidate in (f"ip:{ip}", f"login:{key}"):
        result = limiter.check(candidate)
        if not result.allowed:
            raise RateLimitedError(
                headers={"Retry-After": str(result.retry_after_seconds)}
            )


def check_rate_limit(
    name: str, key: str, *, max_events: int, window_seconds: int
) -> None:
    """Limite pontual para rotas sensíveis sem sessão (ex.: registro de agente)."""
    limiter = _limiters.register(name, max_events=max_events, window_seconds=window_seconds)
    result = limiter.check(key)
    if not result.allowed:
        raise RateLimitedError(headers={"Retry-After": str(result.retry_after_seconds)})


def enforce_agent_rate_limit(
    request: Request, ctx: CurrentAgent, settings: AppSettings
) -> None:
    limiter = _limiters.register(
        "agent",
        max_events=settings.agent_max_requests_per_minute,
        window_seconds=60,
    )
    result = limiter.check(f"agent:{ctx.credential.id}")
    if not result.allowed:
        raise RateLimitedError(headers={"Retry-After": str(result.retry_after_seconds)})


AgentRateLimited = Annotated[None, Depends(enforce_agent_rate_limit)]
