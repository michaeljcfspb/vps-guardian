"""Testes de integração do dashboard e séries temporais (MySQL real)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.telemetry import HostMetric
from tests.integration.conftest import API

pytestmark = pytest.mark.integration


def _agent(admin_client, name: str) -> tuple[str, str]:
    created = admin_client.post(
        f"{API}/servers", json={"name": name, "ip_address": "203.0.113.90"}
    )
    assert created.status_code == 201, created.text
    server_id = created.json()["id"]
    token = admin_client.post(
        f"{API}/servers/{server_id}/provisioning-token"
    ).json()["token"]
    registered = admin_client.client.post(
        f"{API}/agent/register",
        json={"provisioning_token": token, "agent_version": "0.3.0"},
    )
    assert registered.status_code == 201, registered.text
    return server_id, registered.json()["credential"]


def _payload(collected_at: datetime, *, cpu: float, ram: float, disk: float) -> dict[str, object]:
    return {
        "collected_at": collected_at.isoformat(),
        "agent_version": "0.3.0",
        "host": {
            "cpu_percent": cpu,
            "cpu_cores": 2,
            "load_1": 0.2,
            "load_5": 0.2,
            "load_15": 0.2,
            "ram_total_bytes": 4_000_000_000,
            "ram_used_bytes": int(4_000_000_000 * ram / 100),
            "ram_available_bytes": int(4_000_000_000 * (100 - ram) / 100),
            "ram_percent": ram,
            "swap_total_bytes": 0,
            "swap_used_bytes": 0,
            "swap_percent": 0,
            "uptime_seconds": 5_000,
            "process_count": 90,
        },
        "disks": [
            {
                "mount_point": "/",
                "filesystem": "ext4",
                "total_bytes": 100_000,
                "used_bytes": int(100_000 * disk / 100),
                "free_bytes": int(100_000 * (100 - disk) / 100),
                "used_percent": disk,
            }
        ],
        "networks": [
            {
                "interface": "eth0",
                "rx_bytes": 10,
                "tx_bytes": 20,
                "rx_rate_bps": 800,
                "tx_rate_bps": 1_600,
            }
        ],
    }


def _send(client, credential: str, body: dict[str, object]):
    return client.post(
        f"{API}/agent/metrics",
        headers={"Authorization": f"Bearer {credential}"},
        json=body,
    )


def test_dashboard_requires_authentication(client) -> None:
    assert client.get(f"{API}/dashboard/summary").status_code == 401
    assert client.get(f"{API}/telemetry/latest").status_code == 401


def test_summary_aggregates_servers_and_averages(admin_client) -> None:
    now = datetime.now(UTC)
    server_a, credential_a = _agent(admin_client, "DASH-A")
    _server_b, credential_b = _agent(admin_client, "DASH-B")

    body_a = _payload(now, cpu=20, ram=40, disk=50)
    body_b = _payload(now, cpu=40, ram=60, disk=70)
    assert _send(admin_client.client, credential_a, body_a).status_code == 200
    assert _send(admin_client.client, credential_b, body_b).status_code == 200

    response = admin_client.client.get(f"{API}/dashboard/summary")
    assert response.status_code == 200
    body = response.json()

    assert body["servers"]["total"] == 2
    assert body["servers"]["online"] == 2
    assert body["averages"]["cpu_percent"] == pytest.approx(30.0)
    assert body["averages"]["ram_percent"] == pytest.approx(50.0)
    assert body["averages"]["disk_percent"] == pytest.approx(60.0)
    assert body["averages"]["servers_considered"] == 2
    assert body["incidents"]["available"] is False
    assert body["last_heartbeat_at"] is not None
    assert body["data_age_seconds"] is not None
    assert body["servers"]["total"] >= 1  # sanity

    # O servidor A existe e aparece no latest.
    latest = admin_client.client.get(f"{API}/telemetry/latest")
    assert latest.status_code == 200
    ids = {item["server_id"] for item in latest.json()}
    assert server_a in ids


def test_metrics_series_returns_bucketed_points(admin_client) -> None:
    now = datetime.now(UTC)
    server_id, credential = _agent(admin_client, "SERIES")

    for offset in (240, 120, 30):
        payload = _payload(now - timedelta(seconds=offset), cpu=10, ram=20, disk=30)
        assert _send(admin_client.client, credential, payload).status_code == 200

    response = admin_client.client.get(f"{API}/servers/{server_id}/metrics?window=1h")
    assert response.status_code == 200
    body = response.json()
    assert body["window"] == "1h"
    assert body["step_seconds"] == 60
    assert len(body["points"]) >= 1
    first = body["points"][0]
    assert set(first) >= {"at", "cpu_percent", "ram_percent", "disk_percent"}


def test_metrics_series_rejects_invalid_window(admin_client) -> None:
    server_id, _credential = _agent(admin_client, "SERIES-WINDOW")
    response = admin_client.client.get(f"{API}/servers/{server_id}/metrics?window=99h")
    assert response.status_code == 422


def test_heartbeat_history_endpoint(admin_client) -> None:
    server_id, credential = _agent(admin_client, "BEATS")
    for _ in range(2):
        admin_client.client.post(
            f"{API}/agent/heartbeat",
            headers={"Authorization": f"Bearer {credential}"},
            json={
                "sent_at": datetime.now(UTC).isoformat(),
                "agent_version": "0.3.0",
                "uptime_seconds": 1_000,
            },
        )

    response = admin_client.client.get(f"{API}/servers/{server_id}/heartbeats?limit=10")
    assert response.status_code == 200
    beats = response.json()
    assert len(beats) == 2
    assert beats[0]["uptime_seconds"] == 1_000


def test_latest_telemetry_is_idempotent_with_duplicates(admin_client, db_session) -> None:
    now = datetime.now(UTC)
    server_id, credential = _agent(admin_client, "LATEST")
    payload = _payload(now, cpu=15, ram=25, disk=35)

    assert _send(admin_client.client, credential, payload).status_code == 200
    assert _send(admin_client.client, credential, payload).status_code == 200

    total = db_session.scalar(select(func.count()).select_from(HostMetric))
    assert total == 1

    latest = admin_client.client.get(f"{API}/telemetry/latest").json()
    item = next(entry for entry in latest if entry["server_id"] == server_id)
    assert item["cpu_percent"] == pytest.approx(15.0)
    assert item["disk_percent"] == pytest.approx(35.0)
