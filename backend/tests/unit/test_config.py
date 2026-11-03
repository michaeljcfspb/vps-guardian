"""Testes de unidade da configuração por ambiente."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

VALID = {
    "secret_key": "s" * 40,
    "database_url": "mysql+pymysql://u:p@db:3306/vps_guardian",
}


def build(**overrides: object) -> Settings:
    data = {**VALID, **overrides}
    return Settings(_env_file=None, **data)  # type: ignore[arg-type]


@pytest.mark.unit
def test_valid_settings_are_accepted() -> None:
    settings = build(app_env="development")
    assert settings.app_env == "development"
    assert settings.is_production is False


@pytest.mark.unit
def test_short_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build(secret_key="curta")


@pytest.mark.unit
def test_database_url_must_be_mysql() -> None:
    with pytest.raises(ValidationError):
        build(database_url="sqlite:///./db.sqlite3")


@pytest.mark.unit
def test_postgres_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build(database_url="postgresql://u:p@db:5432/vps_guardian")


@pytest.mark.unit
def test_wildcard_cors_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build(cors_origins=["*"])


@pytest.mark.unit
def test_cors_accepts_comma_separated_string() -> None:
    settings = build(cors_origins="https://a.exemplo.com,https://b.exemplo.com")
    assert settings.cors_origins == ["https://a.exemplo.com", "https://b.exemplo.com"]


@pytest.mark.unit
def test_cors_rejects_trailing_slash() -> None:
    with pytest.raises(ValidationError):
        build(cors_origins=["https://a.exemplo.com/"])


@pytest.mark.unit
def test_production_forces_secure_cookies_and_hides_docs() -> None:
    settings = build(app_env="production", cookie_secure=False)
    assert settings.secure_cookies is True
    assert settings.docs_enabled is False


@pytest.mark.unit
def test_development_allows_docs() -> None:
    assert build(app_env="development").docs_enabled is True


@pytest.mark.unit
def test_idle_timeout_cannot_exceed_absolute_ttl() -> None:
    with pytest.raises(ValidationError):
        build(session_ttl_minutes=60, session_idle_timeout_minutes=120)


@pytest.mark.unit
def test_repr_does_not_leak_secret_or_password() -> None:
    settings = build(secret_key="segredo-super-secreto-nao-vazar-" + "x" * 20)
    rendered = repr(settings)
    assert "segredo-super-secreto" not in rendered
    assert "u:p@" not in rendered
