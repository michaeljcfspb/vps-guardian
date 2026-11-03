"""Testes de integração da ingestão de telemetria (MySQL real)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.telemetry import AgentHeartbeat, DiskMetric, HostMetric, NetworkMetric
from tests.integration.conftest import API

pytestmark = pytest.mark.integration


def _server(admin_client, name: str = "VPS-METRICS") -> str:
    response = admin_client.post(
        f"{API}/servers", json={"name": name, "ip_address": "203.0.113.70"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _agent(admin_client, name: str = "VPS-METRICS") -> tuple[str, str]:
    server_id = _server(admin_client, name)
    token = admin_client.post(
        f"{API}/servers/{server_id}/provisioning-token"
    ).json()["token"]
    registered = admin_client.client.post(
        f"{API}/agent/register",
        json={"provisioning_token": token, "agent_version": "0.2.0"},
    )
    assert registered.status_code == 201, registered.text
    return server_id, registered.json()["credential"]


def _metrics_payload(collected_at: datetime | None = None) -> dict[str, object]:
    moment = collected_at or datetime.now(UTC)
    return {
        "collected_at": moment.isoformat(),
        "agent_version": "0.2.0",
        "host": {
            "cpu_percent": 23.5,
            "cpu_cores": 4,
            "load_1": 0.5,
            "load_5": 0.4,
            "load_15": 0.3,
            "ram_total_bytes": 8_589_934_592,
            "ram_used_bytes": 4_294_967_296,
            "ram_available_bytes": 4_294_967_296,
            "ram_percent": 50.0,
            "swap_total_bytes": 2_147_483_648,
            "swap_used_bytes": 0,
            "swap_percent": 0.0,
            "uptime_seconds": 86_400,
            "process_count": 150,
        },
        "disks": [
            {
                "mount_point": "/",
                "filesystem": "ext4",
                "total_bytes": 100_000,
                "used_bytes": 40_000,
                "free_bytes": 60_000,
                "used_percent": 40.0,
            }
        ],
        "networks": [
            {
                "interface": "eth0",
                "rx_bytes": 1_000,
                "tx_bytes": 2_000,
                "rx_rate_bps": 800,
                "tx_rate_bps": 1600,
            }
        ],
    }


def _send(client, credential: str, body: dict[str, object]):
    return client.post(
        f"{API}/agent/metrics",
        headers={"Authorization": f"Bearer {credential}"},
        json=body,
    )


def test_metrics_are_persisted(admin_client, db_session) -> None:
    server_id, credential = _agent(admin_client)

    response = _send(admin_client.client, credential, _metrics_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recorded"] is True
    assert body["duplicate"] is False
    assert body["disks_recorded"] == 1
    assert body["networks_recorded"] == 1

    host = db_session.scalar(
        select(HostMetric).where(HostMetric.server_id == server_id)
    )
    assert host is not None
    assert float(host.cpu_percent) == pytest.approx(23.5)
    assert db_session.scalar(select(func.count()).select_from(DiskMetric)) == 1
    assert db_session.scalar(select(func.count()).select_from(NetworkMetric)) == 1

    server = admin_client.client.get(f"{API}/servers/{server_id}").json()
    assert server["last_metrics_at"] is not None


def test_duplicate_collection_is_idempotent(admin_client, db_session) -> None:
    _server_id, credential = _agent(admin_client, "VPS-DUP")
    moment = datetime.now(UTC) - timedelta(minutes=1)

    first = _send(admin_client.client, credential, _metrics_payload(moment))
    second = _send(admin_client.client, credential, _metrics_payload(moment))

    assert first.json()["recorded"] is True
    assert second.json()["recorded"] is False
    assert second.json()["duplicate"] is True
    assert db_session.scalar(select(func.count()).select_from(HostMetric)) == 1


def test_stale_collection_is_rejected(admin_client) -> None:
    _server_id, credential = _agent(admin_client, "VPS-OLD")
    old = datetime.now(UTC) - timedelta(hours=30)

    response = _send(admin_client.client, credential, _metrics_payload(old))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_future_collection_is_rejected(admin_client) -> None:
    _server_id, credential = _agent(admin_client, "VPS-FUTURE")
    future = datetime.now(UTC) + timedelta(minutes=30)

    response = _send(admin_client.client, credential, _metrics_payload(future))
    assert response.status_code == 400


def test_invalid_payload_is_rejected(admin_client) -> None:
    _server_id, credential = _agent(admin_client, "VPS-INVALID")
    body = _metrics_payload()
    body["host"]["cpu_percent"] = 150  # type: ignore[index]

    response = _send(admin_client.client, credential, body)
    assert response.status_code == 422


def test_metrics_require_agent_credential(client) -> None:
    response = client.post(f"{API}/agent/metrics", json=_metrics_payload())
    assert response.status_code == 401


def test_wrong_credential_cannot_inject_into_another_server(admin_client, db_session) -> None:
    first_id, first_credential = _agent(admin_client, "VPS-OWNER")
    second_id, _second_credential = _agent(admin_client, "VPS-VICTIM")

    _send(admin_client.client, first_credential, _metrics_payload())

    assert db_session.scalar(
        select(func.count()).select_from(HostMetric).where(HostMetric.server_id == second_id)
    ) == 0
    assert db_session.scalar(
        select(func.count()).select_from(HostMetric).where(HostMetric.server_id == first_id)
    ) == 1


def test_heartbeat_is_recorded(admin_client, db_session) -> None:
    server_id, credential = _agent(admin_client, "VPS-BEAT")

    response = admin_client.client.post(
        f"{API}/agent/heartbeat",
        headers={"Authorization": f"Bearer {credential}"},
        json={
            "sent_at": datetime.now(UTC).isoformat(),
            "agent_version": "0.2.0",
            "uptime_seconds": 4321,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "online"

    beats = db_session.scalars(
        select(AgentHeartbeat).where(AgentHeartbeat.server_id == server_id)
    ).all()
    assert len(beats) == 1
    assert beats[0].uptime_seconds == 4321


def test_agent_config_enables_metrics_feature(admin_client) -> None:
    _server_id, credential = _agent(admin_client, "VPS-CONFIG")
    response = admin_client.client.get(
        f"{API}/agent/config", headers={"Authorization": f"Bearer {credential}"}
    )
    assert response.status_code == 200
    assert response.json()["features"]["metrics"] is True
