"""Testes de integração do provisionamento de agentes (MySQL real).

Cobrem os critérios da Fase 3 do ROADMAP: token de provisionamento de uso único,
identidade exclusiva por servidor, revogação, rotação e ausência de segredos em
consultas comuns.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.security import utc_now
from app.models.credential import ProvisioningToken
from tests.integration.conftest import API

pytestmark = pytest.mark.integration


def _server(admin_client, name: str = "VPS-PILOTO") -> str:
    response = admin_client.post(
        f"{API}/servers",
        json={"name": name, "ip_address": "203.0.113.50", "panel": "portainer"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _token(admin_client, server_id: str) -> str:
    response = admin_client.post(f"{API}/servers/{server_id}/provisioning-token")
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _register(client, token: str, *, version: str = "0.1.0"):
    return client.post(
        f"{API}/agent/register",
        json={
            "provisioning_token": token,
            "agent_version": version,
            "hostname": "vps-piloto.exemplo.com",
            "os_name": "Ubuntu",
            "os_version": "24.04",
            "kernel": "6.8.0-45-generic",
            "architecture": "x86_64",
        },
    )


def _heartbeat(client, credential: str, *, skew_seconds: int = 0):
    sent_at = datetime.now(UTC) - timedelta(seconds=skew_seconds)
    return client.post(
        f"{API}/agent/heartbeat",
        headers={"Authorization": f"Bearer {credential}"},
        json={
            "sent_at": sent_at.isoformat(),
            "agent_version": "0.1.0",
            "uptime_seconds": 12345,
        },
    )


def test_provisioning_token_is_returned_once(admin_client) -> None:
    server_id = _server(admin_client)
    response = admin_client.post(f"{API}/servers/{server_id}/provisioning-token")
    assert response.status_code == 200
    body = response.json()
    assert len(body["token"]) >= 40
    assert body["register_url"].endswith("/agent/register")
    assert body["token_prefix"] == body["token"][:12]

    # Consultas comuns ao servidor não devolvem o token.
    detail = admin_client.client.get(f"{API}/servers/{server_id}")
    assert "token" not in detail.text.lower()
    assert detail.json()["active_credentials"] == 0


def test_register_creates_credential_and_heartbeat_turns_online(admin_client) -> None:
    server_id = _server(admin_client)
    token = _token(admin_client, server_id)

    registered = _register(admin_client.client, token)
    assert registered.status_code == 201, registered.text
    credential = registered.json()["credential"]
    assert len(credential) >= 40

    beat = _heartbeat(admin_client.client, credential)
    assert beat.status_code == 200, beat.text
    assert beat.json()["status"] == "online"

    detail = admin_client.client.get(f"{API}/servers/{server_id}").json()
    assert detail["status"] == "online"
    assert detail["last_heartbeat_at"] is not None
    assert detail["os_name"] == "Ubuntu"
    assert detail["agent_version"] == "0.1.0"
    assert detail["active_credentials"] == 1


def test_provisioning_token_cannot_be_reused(admin_client) -> None:
    server_id = _server(admin_client)
    token = _token(admin_client, server_id)

    assert _register(admin_client.client, token).status_code == 201
    second = _register(admin_client.client, token)
    assert second.status_code == 401


def test_invalid_provisioning_token_is_rejected(admin_client) -> None:
    _server(admin_client)
    response = _register(admin_client.client, "token-invalido-" + "x" * 40)
    assert response.status_code == 401


def test_expired_provisioning_token_is_rejected(admin_client, db_session) -> None:
    server_id = _server(admin_client)
    token = _token(admin_client, server_id)

    db_session.execute(
        update(ProvisioningToken).values(expires_at=utc_now() - timedelta(minutes=1))
    )
    db_session.commit()

    assert _register(admin_client.client, token).status_code == 401


def test_new_token_invalidates_previous(admin_client) -> None:
    server_id = _server(admin_client)
    first = _token(admin_client, server_id)
    second = _token(admin_client, server_id)
    assert first != second

    assert _register(admin_client.client, first).status_code == 401
    assert _register(admin_client.client, second).status_code == 201


def test_credential_is_bound_to_its_server(admin_client) -> None:
    server_a = _server(admin_client, "VPS-A")
    server_b = _server(admin_client, "VPS-B")
    credential_a = _register(admin_client.client, _token(admin_client, server_a)).json()[
        "credential"
    ]

    beat = _heartbeat(admin_client.client, credential_a)
    assert beat.json()["server_id"] == server_a

    detail_b = admin_client.client.get(f"{API}/servers/{server_b}").json()
    assert detail_b["last_heartbeat_at"] is None
    assert detail_b["status"] == "unprovisioned"


def test_rotate_revokes_previous_credential(admin_client) -> None:
    server_id = _server(admin_client)
    old = _register(admin_client.client, _token(admin_client, server_id)).json()["credential"]

    rotated = admin_client.post(f"{API}/servers/{server_id}/rotate-credential")
    assert rotated.status_code == 200
    new = rotated.json()["credential"]
    assert rotated.json()["revoked_previous"] == 1
    assert new != old

    assert _heartbeat(admin_client.client, old).status_code == 401
    assert _heartbeat(admin_client.client, new).status_code == 200


def test_revoke_all_credentials(admin_client) -> None:
    server_id = _server(admin_client)
    credential = _register(admin_client.client, _token(admin_client, server_id)).json()[
        "credential"
    ]
    assert _heartbeat(admin_client.client, credential).status_code == 200

    revoked = admin_client.post(f"{API}/servers/{server_id}/credentials/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] == 1
    assert _heartbeat(admin_client.client, credential).status_code == 401


def test_paused_server_rejects_telemetry(admin_client) -> None:
    server_id = _server(admin_client)
    credential = _register(admin_client.client, _token(admin_client, server_id)).json()[
        "credential"
    ]
    admin_client.post(f"{API}/servers/{server_id}/pause")

    response = _heartbeat(admin_client.client, credential)
    assert response.status_code == 403


def test_heartbeat_without_credential_is_rejected(client) -> None:
    response = client.post(
        f"{API}/agent/heartbeat",
        json={
            "sent_at": datetime.now(UTC).isoformat(),
            "agent_version": "0.1.0",
            "uptime_seconds": 1,
        },
    )
    assert response.status_code == 401


def test_heartbeat_rejects_absurd_clock_skew(admin_client) -> None:
    server_id = _server(admin_client)
    credential = _register(admin_client.client, _token(admin_client, server_id)).json()[
        "credential"
    ]
    response = _heartbeat(admin_client.client, credential, skew_seconds=90_000)
    assert response.status_code == 400


def test_agent_config_matches_server_settings(admin_client) -> None:
    server_id = _server(admin_client)
    credential = _register(admin_client.client, _token(admin_client, server_id)).json()[
        "credential"
    ]
    response = admin_client.client.get(
        f"{API}/agent/config", headers={"Authorization": f"Bearer {credential}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == server_id
    assert body["collection_interval_seconds"] == 30
    # Fase 4+ ainda não habilitada: recursos desligados explicitamente.
    assert body["features"]["metrics"] is False


def test_credentials_list_exposes_only_prefix(admin_client) -> None:
    server_id = _server(admin_client)
    credential = _register(admin_client.client, _token(admin_client, server_id)).json()[
        "credential"
    ]
    response = admin_client.client.get(f"{API}/servers/{server_id}/credentials")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["token_prefix"] == credential[:12]
    assert credential not in response.text
