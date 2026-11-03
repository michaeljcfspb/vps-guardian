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


# --- URL montada a partir de partes (modo de instalação recomendado) ---------


def build_from_parts(**overrides: object) -> Settings:
    data = {
        "secret_key": "s" * 40,
        "database_url": None,
        "db_host": "mysql",
        "db_name": "vps_guardian",
        "db_user": "guardian",
        "db_password": "senha-com-caracteres@#/:",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)  # type: ignore[arg-type]


@pytest.mark.unit
def test_database_url_is_built_from_parts() -> None:
    settings = build_from_parts()
    assert settings.database_url is not None
    assert settings.database_url.startswith("mysql+pymysql://guardian:")
    assert settings.database_url.endswith("@mysql:3306/vps_guardian")


@pytest.mark.unit
def test_password_special_characters_are_url_encoded() -> None:
    settings = build_from_parts(db_password="p@ss#word/1")
    url = settings.database_url or ""
    # '@' e '/' da senha não podem quebrar a URL.
    assert url.count("@") == 1
    assert "%40" in url and "%23" in url and "%2F" in url
    assert url.endswith("@mysql:3306/vps_guardian")


@pytest.mark.unit
def test_empty_database_url_falls_back_to_parts() -> None:
    settings = build_from_parts(database_url="")
    assert settings.database_url is not None
    assert settings.database_url.endswith("/vps_guardian")


@pytest.mark.unit
def test_missing_parts_are_reported() -> None:
    with pytest.raises(ValidationError) as exc:
        build_from_parts(db_host=None, db_password=None)
    message = str(exc.value)
    assert "GUARDIAN_DB_HOST" in message
    assert "GUARDIAN_DB_PASSWORD" in message


@pytest.mark.unit
def test_db_name_rejects_unsafe_identifier() -> None:
    with pytest.raises(ValidationError):
        build_from_parts(db_name="vps_guardian; DROP DATABASE x")


@pytest.mark.unit
def test_built_url_repr_hides_password() -> None:
    settings = build_from_parts(db_password="nao-pode-vazar-123")
    assert "nao-pode-vazar-123" not in repr(settings)
