"""Configuração compartilhada dos testes.

Regras (ver ADR-0001):
- Testes de unidade **não** usam banco de dados.
- Testes de integração exigem MySQL real via ``GUARDIAN_TEST_DATABASE_URL``; sem ela
  são **skipped** com motivo explícito, nunca aprovados por omissão.
- SQLite jamais é usado como substituto do MySQL (PRD §17.2.4).
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("GUARDIAN_APP_ENV", "test")
os.environ.setdefault("GUARDIAN_SECRET_KEY", "test-secret-key-" + "a" * 40)
os.environ.setdefault(
    "GUARDIAN_DATABASE_URL",
    "mysql+pymysql://guardian:guardian@127.0.0.1:3306/vps_guardian_test",
)
os.environ.setdefault("GUARDIAN_LOG_LEVEL", "WARNING")
os.environ.setdefault("GUARDIAN_LOG_JSON", "true")
os.environ.setdefault("GUARDIAN_LOGIN_MAX_ATTEMPTS", "5")

import pytest  # noqa: E402

from app.api.deps import reset_limiters  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(autouse=True)
def _isolate_rate_limiters() -> None:
    """Cada teste começa com janelas de rate limit vazias."""
    reset_limiters()
    yield
    reset_limiters()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("GUARDIAN_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip(
            "GUARDIAN_TEST_DATABASE_URL não definida: teste de integração exige MySQL real "
            "(ADR-0001). Este teste NÃO foi aprovado."
        )
    if not url.startswith("mysql"):
        pytest.fail("Somente MySQL é aceito nos testes de integração (PRD §17.2.4)")
    return url
