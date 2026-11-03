"""Fixtures de integração — exigem MySQL real (ADR-0001).

A URL vem de ``GUARDIAN_TEST_DATABASE_URL``. Sem ela, todos os testes deste diretório
são *skipped* com motivo explícito.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from alembic import command
from app.core.config import get_settings
from app.core.security import hash_password, utc_now
from app.db.session import get_db
from app.main import create_app
from app.models.user import User

BACKEND_DIR = Path(__file__).resolve().parents[2]
API = "/api/v1"
ADMIN_EMAIL = "admin@teste.local"
ADMIN_PASSWORD = "SenhaDeTeste!2026"
OPERATOR_EMAIL = "operador@teste.local"


def _generate_password() -> str:
    """Senha fixa apenas para testes; nunca usada fora de banco de teste."""
    return ADMIN_PASSWORD


@dataclass
class AuthedClient:
    """Cliente com sessão ativa e o token CSRF para o header double-submit."""

    client: TestClient
    csrf: str

    @property
    def headers(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf}

    def post(self, url: str, **kwargs: object):  # noqa: ANN201
        headers = {**self.headers, **kwargs.pop("headers", {})}  # type: ignore[arg-type]
        return self.client.post(url, headers=headers, **kwargs)  # type: ignore[arg-type]

    def patch(self, url: str, **kwargs: object):  # noqa: ANN201
        headers = {**self.headers, **kwargs.pop("headers", {})}  # type: ignore[arg-type]
        return self.client.patch(url, headers=headers, **kwargs)  # type: ignore[arg-type]

    def delete(self, url: str, **kwargs: object):  # noqa: ANN201
        headers = {**self.headers, **kwargs.pop("headers", {})}  # type: ignore[arg-type]
        return self.client.delete(url, headers=headers, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Iterator[Engine]:
    """Aplica as migrations no banco de teste (MySQL real) antes da sessão."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", test_database_url.replace("%", "%%"))
    command.upgrade(config, "head")

    engine = create_engine(test_database_url, poolclass=NullPool, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Sessão isolada: cada teste roda dentro de uma transação desfeita no final."""
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()
        if outer.is_active:
            outer.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    application = create_app(get_settings())
    application.dependency_overrides[get_db] = lambda: db_session
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        email=ADMIN_EMAIL,
        name="Administrador de Teste",
        password_hash=hash_password(_generate_password()),
        role="admin",
        is_active=True,
        created_at=utc_now(),
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def operator_user(db_session: Session) -> User:
    user = User(
        email=OPERATOR_EMAIL,
        name="Operador de Teste",
        password_hash=hash_password(ADMIN_PASSWORD),
        role="operator",
        is_active=True,
        created_at=utc_now(),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _login(client: TestClient, email: str, password: str) -> AuthedClient:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    csrf = client.cookies.get("guardian_csrf")
    assert csrf, "cookie CSRF não foi definido"
    return AuthedClient(client=client, csrf=csrf)


@pytest.fixture
def admin_client(client: TestClient, admin_user: User) -> AuthedClient:
    return _login(client, admin_user.email, ADMIN_PASSWORD)


@pytest.fixture
def operator_client(client: TestClient, operator_user: User) -> AuthedClient:
    return _login(client, operator_user.email, ADMIN_PASSWORD)


@pytest.fixture(autouse=True)
def _clean_env_flags() -> Iterator[None]:
    os.environ.pop("GUARDIAN_ADMIN_PASSWORD", None)
    yield
