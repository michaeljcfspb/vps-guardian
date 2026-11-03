"""Testes de integração de autenticação (MySQL real)."""

from __future__ import annotations

import pytest

from app.models.audit import AuditLog
from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, API

pytestmark = pytest.mark.integration


def test_login_success_sets_cookies_and_audits(client, admin_user, db_session) -> None:
    response = client.post(
        f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == ADMIN_EMAIL
    assert "password" not in str(body).lower()

    session_cookie = client.cookies.get("guardian_session")
    csrf_cookie = client.cookies.get("guardian_csrf")
    assert session_cookie and csrf_cookie
    assert session_cookie != csrf_cookie

    actions = {
        row.action for row in db_session.query(AuditLog).all()
    }
    assert "auth.login.success" in actions


def test_login_failure_is_generic_and_audited(client, admin_user, db_session) -> None:
    response = client.post(
        f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "SenhaErrada!2026"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "senha" not in response.text.lower()

    actions = {row.action for row in db_session.query(AuditLog).all()}
    assert "auth.login.failure" in actions


def test_login_unknown_email_returns_same_error(client) -> None:
    response = client.post(
        f"{API}/auth/login", json={"email": "ninguem@teste.local", "password": "Qualquer!2026"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Credenciais inválidas"


def test_me_requires_session(client) -> None:
    response = client.get(f"{API}/auth/me")
    assert response.status_code == 401


def test_me_returns_user_when_authenticated(admin_client) -> None:
    response = admin_client.client.get(f"{API}/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == ADMIN_EMAIL


def test_logout_requires_csrf(admin_client) -> None:
    response = admin_client.client.post(f"{API}/auth/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_logout_revokes_session(admin_client) -> None:
    response = admin_client.post(f"{API}/auth/logout")
    assert response.status_code == 204
    assert admin_client.client.get(f"{API}/auth/me").status_code == 401


def test_login_is_rate_limited(client, admin_user, settings) -> None:
    for _ in range(settings.login_max_attempts):
        client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "Errada!2026"})

    blocked = client.post(
        f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_session_cookie_is_httponly(client, admin_user) -> None:
    response = client.post(
        f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    raw = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in raw if c.startswith("guardian_session="))
    assert "HttpOnly" in session_cookie
    csrf_cookie = next(c for c in raw if c.startswith("guardian_csrf="))
    assert "HttpOnly" not in csrf_cookie
