"""Diagnóstico de configuração: mensagens sem vazamento de valores (PRD §11)."""

from __future__ import annotations

import pytest

from app.cli import main as cli_main
from app.core.config import ConfigurationError, get_settings, reset_settings_cache

DB_PASSWORD = "SenhaDoBanco!MuitoSecreta#2026"
DB_HOST = "10.0.0.55"


def _full_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARDIAN_APP_ENV", "production")
    monkeypatch.setenv("GUARDIAN_DB_HOST", DB_HOST)
    monkeypatch.setenv("GUARDIAN_DB_PORT", "3306")
    monkeypatch.setenv("GUARDIAN_DB_NAME", "vps_guardian")
    monkeypatch.setenv("GUARDIAN_DB_USER", "guardian")
    monkeypatch.setenv("GUARDIAN_DB_PASSWORD", DB_PASSWORD)
    monkeypatch.delenv("GUARDIAN_DATABASE_URL", raising=False)


@pytest.mark.unit
def test_missing_secret_key_is_named_but_value_never_leaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _full_db_env(monkeypatch)
    monkeypatch.delenv("GUARDIAN_SECRET_KEY", raising=False)
    reset_settings_cache()

    with pytest.raises(ConfigurationError) as excinfo:
        get_settings()

    report = excinfo.value.report()
    assert "GUARDIAN_SECRET_KEY" in report
    assert "obrigatório" in report
    # Nenhum valor sensível pode aparecer no relatório.
    assert DB_PASSWORD not in report
    assert DB_HOST not in report


@pytest.mark.unit
def test_short_secret_key_reports_minimum_length(monkeypatch: pytest.MonkeyPatch) -> None:
    _full_db_env(monkeypatch)
    monkeypatch.setenv("GUARDIAN_SECRET_KEY", "curta")
    reset_settings_cache()

    with pytest.raises(ConfigurationError) as excinfo:
        get_settings()

    report = excinfo.value.report()
    assert "GUARDIAN_SECRET_KEY" in report
    assert "32" in report
    assert "curta" not in report


@pytest.mark.unit
def test_original_validation_error_is_not_chained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O traceback não pode trazer o ValidationError original (contém input_value)."""
    _full_db_env(monkeypatch)
    monkeypatch.delenv("GUARDIAN_SECRET_KEY", raising=False)
    reset_settings_cache()

    with pytest.raises(ConfigurationError) as excinfo:
        get_settings()

    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


@pytest.mark.unit
def test_cli_exits_with_clean_message(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    _full_db_env(monkeypatch)
    monkeypatch.delenv("GUARDIAN_SECRET_KEY", raising=False)
    reset_settings_cache()

    exit_code = cli_main(["check"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "GUARDIAN_SECRET_KEY" in captured.err
    assert DB_PASSWORD not in captured.err
    assert "Traceback" not in captured.err
