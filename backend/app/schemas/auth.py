"""Schemas de autenticação do painel.

O token CSRF nunca é devolvido no corpo: ele vive no cookie ``guardian_csrf``
(legível por JS, SameSite=Strict) e é reenviado no header ``X-CSRF-Token``.
"""

from __future__ import annotations

from pydantic import EmailStr, Field, field_validator

from app.core.enums import UserRole
from app.schemas.common import ApiModel, UtcDatetime


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserRead(ApiModel):
    id: int
    email: str
    name: str
    role: UserRole
    is_active: bool
    last_login_at: UtcDatetime | None = None
    created_at: UtcDatetime


class LoginResponse(ApiModel):
    user: UserRead


class MeResponse(ApiModel):
    user: UserRead
    session_expires_at: UtcDatetime
