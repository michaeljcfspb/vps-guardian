"""Testes de integração de servidores e autorização (MySQL real)."""

from __future__ import annotations

import pytest

from tests.integration.conftest import API

pytestmark = pytest.mark.integration


def _payload(name: str = "VPS-01", **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": name,
        "hostname": name.lower() + ".exemplo.com",
        "ip_address": "203.0.113.10",
        "environment": "production",
        "panel": "easypanel",
        "tags": ["web"],
    }
    data.update(overrides)
    return data


def test_list_requires_authentication(client) -> None:
    assert client.get(f"{API}/servers").status_code == 401


def test_create_requires_csrf(client, admin_user) -> None:
    login = client.post(
        f"{API}/auth/login",
        json={"email": admin_user.email, "password": "SenhaDeTeste!2026"},
    )
    assert login.status_code == 200
    response = client.post(f"{API}/servers", json=_payload())
    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Token CSRF ausente ou inválido"


def test_create_and_read_server(admin_client) -> None:
    created = admin_client.post(f"{API}/servers", json=_payload())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "unprovisioned"
    assert body["active_credentials"] == 0
    assert body["hostname"] == "vps-01.exemplo.com"
    assert body["collection_interval_seconds"] == 30

    listed = admin_client.client.get(f"{API}/servers")
    assert listed.status_code == 200
    page = listed.json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == body["id"]

    detail = admin_client.client.get(f"{API}/servers/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "VPS-01"


def test_duplicate_name_returns_conflict(admin_client) -> None:
    assert admin_client.post(f"{API}/servers", json=_payload()).status_code == 201
    duplicated = admin_client.post(f"{API}/servers", json=_payload())
    assert duplicated.status_code == 409


def test_invalid_payload_returns_validation_details(admin_client) -> None:
    response = admin_client.post(f"{API}/servers", json=_payload(ip_address="nao-e-ip"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["fields"]


def test_unknown_server_returns_404(admin_client) -> None:
    assert admin_client.client.get(f"{API}/servers/inexistente").status_code == 404


def test_patch_updates_only_sent_fields(admin_client) -> None:
    server_id = admin_client.post(f"{API}/servers", json=_payload()).json()["id"]
    response = admin_client.patch(
        f"{API}/servers/{server_id}", json={"notes": "janela de manutenção"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["notes"] == "janela de manutenção"
    assert body["name"] == "VPS-01"


def test_patch_rejects_interval_invariant(admin_client) -> None:
    server_id = admin_client.post(f"{API}/servers", json=_payload()).json()["id"]
    response = admin_client.patch(
        f"{API}/servers/{server_id}",
        json={"collection_interval_seconds": 120, "heartbeat_timeout_seconds": 90},
    )
    assert response.status_code == 400


def test_operator_can_read_but_not_write(operator_client) -> None:
    assert operator_client.client.get(f"{API}/servers").status_code == 200
    created = operator_client.post(f"{API}/servers", json=_payload())
    assert created.status_code == 403


def test_pause_and_resume_cycle(admin_client) -> None:
    server_id = admin_client.post(f"{API}/servers", json=_payload()).json()["id"]

    paused = admin_client.post(f"{API}/servers/{server_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = admin_client.post(f"{API}/servers/{server_id}/resume")
    assert resumed.status_code == 200
    # Nunca registrado: volta para "não provisionado", não para "online".
    assert resumed.json()["status"] == "unprovisioned"


def test_disable_blocks_provisioning(admin_client) -> None:
    server_id = admin_client.post(f"{API}/servers", json=_payload()).json()["id"]
    assert admin_client.post(f"{API}/servers/{server_id}/disable").json()["status"] == "disabled"
    response = admin_client.post(f"{API}/servers/{server_id}/provisioning-token")
    assert response.status_code == 400


def test_filters_and_pagination(admin_client) -> None:
    for index in range(3):
        panel = "portainer" if index == 1 else "easypanel"
        admin_client.post(
            f"{API}/servers",
            json=_payload(name=f"VPS-{index:02d}", panel=panel),
        )

    filtered = admin_client.client.get(f"{API}/servers?panel=portainer")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    paged = admin_client.client.get(f"{API}/servers?limit=2&offset=0")
    assert len(paged.json()["items"]) == 2
    assert paged.json()["total"] == 3

    searched = admin_client.client.get(f"{API}/servers?search=VPS-02")
    assert searched.json()["total"] == 1


def test_audit_trail_is_admin_only(admin_client, operator_client) -> None:
    admin_client.post(f"{API}/servers", json=_payload())

    forbidden = operator_client.client.get(f"{API}/system/audit-logs")
    assert forbidden.status_code == 403

    allowed = admin_client.client.get(f"{API}/system/audit-logs?action=server.created")
    assert allowed.status_code == 200
    actions = [item["action"] for item in allowed.json()["items"]]
    assert "server.created" in actions


def test_server_payload_never_contains_secrets(admin_client) -> None:
    created = admin_client.post(f"{API}/servers", json=_payload())
    serialized = created.text.lower()
    for forbidden in ("credential", "token", "password"):
        assert forbidden not in serialized
