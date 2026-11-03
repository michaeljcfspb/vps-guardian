"""Autenticação do painel: verificação de senha, criação e revogação de sessões."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    utc_now,
    verify_password,
)
from app.models.user import User, UserSession

# Hash descartável para igualar o custo de verificação quando o e-mail não existe,
# evitando um oráculo de tempo que revelaria contas cadastradas.
_DUMMY_HASH: str | None = None
_TOUCH_INTERVAL_SECONDS = 60
_MAX_USER_AGENT = 255


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("timing-equalization-placeholder")
    return _DUMMY_HASH


def normalize_email(email: str) -> str:
    return email.strip().lower()


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def authenticate(db: Session, *, email: str, password: str) -> User | None:
    """Retorna o usuário quando e-mail+senha conferem. Não revela o motivo da falha."""
    user = find_user_by_email(db, email)
    if user is None:
        verify_password(_dummy_hash(), password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    if not user.is_active:
        return None
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def create_session(
    db: Session,
    *,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[UserSession, str, str]:
    """Cria a sessão e devolve ``(sessão, token, csrf_token)``.

    Os dois tokens retornados estão em claro e existem apenas neste momento; no banco
    fica somente o SHA-256 de cada um (ADR-0003).
    """
    moment = now or utc_now()

    # Limpeza oportunista: sessões já expiradas deste usuário não têm valor.
    db.execute(
        delete(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.expires_at < moment,
        )
    )

    token = generate_token()
    csrf_token = generate_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token_hash=hash_token(csrf_token),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:_MAX_USER_AGENT] or None,
        created_at=moment,
        last_seen_at=moment,
        expires_at=moment + timedelta(minutes=settings.session_ttl_minutes),
        idle_expires_at=moment + timedelta(minutes=settings.session_idle_timeout_minutes),
    )
    user.last_login_at = moment
    db.add(session)
    return session, token, csrf_token


def load_session(
    db: Session, *, token: str, settings: Settings, now: datetime | None = None
) -> tuple[UserSession, User] | None:
    """Carrega a sessão válida (não revogada, não expirada) e o usuário ativo."""
    moment = now or utc_now()
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(token))
    )
    if session is None or not session.is_active(moment):
        return None

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None

    if (moment - session.last_seen_at).total_seconds() >= _TOUCH_INTERVAL_SECONDS:
        session.last_seen_at = moment
        session.idle_expires_at = moment + timedelta(
            minutes=settings.session_idle_timeout_minutes
        )
    return session, user


def revoke_session(
    db: Session, *, session: UserSession, reason: str, now: datetime | None = None
) -> None:
    if session.revoked_at is None:
        session.revoked_at = now or utc_now()
        session.revoked_reason = reason[:120]


def revoke_all_sessions(db: Session, *, user_id: int, reason: str) -> int:
    now = utc_now()
    sessions = db.scalars(
        select(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
        )
    ).all()
    for session in sessions:
        revoke_session(db, session=session, reason=reason, now=now)
    return len(sessions)


def csrf_matches(session: UserSession, provided_token: str | None) -> bool:
    if not provided_token:
        return False
    return hash_token(provided_token) == session.csrf_token_hash


def session_expiry(session: UserSession) -> datetime:
    return min(session.expires_at, session.idle_expires_at)
