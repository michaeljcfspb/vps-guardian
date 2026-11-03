"""Smoke test das rotas do painel sem banco de dados.

Motivo de existir: um atributo inexistente em ``Settings`` (``session_cookie_name``)
só aparecia em tempo de execução — nenhum teste de unidade cobria o caminho da
dependência de sessão, e os testes de integração ficavam *skipped* sem MySQL. O
resultado em produção era **500 em todas as rotas /api**.

Estes testes criam a aplicação real e chamam as rotas sem cookie: a sessão é
verificada antes de qualquer consulta ao banco, então o retorno esperado é 401.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    application = create_app(get_settings())
    with TestClient(application, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.mark.unit
def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    ["/api/v1/auth/me", "/api/v1/servers", "/api/v1/dashboard/summary", "/api/v1/telemetry/latest"],
)
def test_protected_routes_require_session(client: TestClient, path: str) -> None:
    response = client.get(path)
    # 401 (e não 500): prova que a dependência de sessão resolveu até o fim.
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.unit
def test_login_without_body_is_validation_error(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422


@pytest.mark.unit
def test_settings_expose_session_cookie_name() -> None:
    """Guarda contra regressão do atributo que faltava."""
    settings = get_settings()
    assert isinstance(settings.session_cookie_name, str)
    assert settings.session_cookie_name
