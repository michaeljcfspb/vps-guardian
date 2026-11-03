"""Testes de unidade do contrato de telemetria (sem banco)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.agent import (
    AgentMetricsRequest,
    DiskMetricIn,
    HostMetricIn,
    NetworkMetricIn,
)

HOST = {
    "cpu_percent": 12.5,
    "cpu_cores": 4,
    "load_1": 0.5,
    "load_5": 0.4,
    "load_15": 0.3,
    "ram_total_bytes": 8000,
    "ram_used_bytes": 3000,
    "ram_available_bytes": 5000,
    "ram_percent": 37.5,
    "swap_total_bytes": 2000,
    "swap_used_bytes": 500,
    "swap_percent": 25.0,
    "uptime_seconds": 3600,
    "process_count": 120,
}


def payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "collected_at": datetime.now(UTC).isoformat(),
        "agent_version": "0.2.0",
        "host": dict(HOST),
        "disks": [],
        "networks": [],
    }
    data.update(overrides)
    return data


@pytest.mark.unit
def test_minimal_payload_is_accepted() -> None:
    model = AgentMetricsRequest.model_validate(payload())
    assert model.host.cpu_cores == 4
    assert model.disks == []


@pytest.mark.unit
def test_collected_at_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        AgentMetricsRequest.model_validate(
            payload(collected_at=datetime(2026, 11, 3, 12, 0, 0).isoformat())
        )


@pytest.mark.unit
def test_cpu_percent_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HostMetricIn(**{**HOST, "cpu_percent": 101})


@pytest.mark.unit
def test_used_memory_above_total_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HostMetricIn(**{**HOST, "ram_used_bytes": 9000})


@pytest.mark.unit
def test_swap_used_above_total_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HostMetricIn(**{**HOST, "swap_used_bytes": 3000})


@pytest.mark.unit
def test_unknown_host_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        HostMetricIn(**{**HOST, "gpu_percent": 10})


@pytest.mark.unit
def test_disk_consistency() -> None:
    with pytest.raises(ValidationError):
        DiskMetricIn(
            mount_point="/",
            total_bytes=100,
            used_bytes=150,
            free_bytes=10,
            used_percent=50,
        )


@pytest.mark.unit
def test_disk_mount_point_control_chars_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DiskMetricIn(
            mount_point="/dados\x01",
            total_bytes=100,
            used_bytes=50,
            free_bytes=50,
            used_percent=50,
        )


@pytest.mark.unit
def test_network_interface_pattern() -> None:
    assert NetworkMetricIn(interface="eth0", rx_bytes=1, tx_bytes=2).interface == "eth0"
    with pytest.raises(ValidationError):
        NetworkMetricIn(interface="placa de rede", rx_bytes=1, tx_bytes=2)


@pytest.mark.unit
def test_too_many_disks_are_rejected() -> None:
    disks = [
        {
            "mount_point": f"/m{index}",
            "total_bytes": 100,
            "used_bytes": 50,
            "free_bytes": 50,
            "used_percent": 50,
        }
        for index in range(65)
    ]
    with pytest.raises(ValidationError):
        AgentMetricsRequest.model_validate(payload(disks=disks))


@pytest.mark.unit
def test_too_many_interfaces_are_rejected() -> None:
    networks = [
        {"interface": f"eth{index}", "rx_bytes": 1, "tx_bytes": 2} for index in range(33)
    ]
    with pytest.raises(ValidationError):
        AgentMetricsRequest.model_validate(payload(networks=networks))
