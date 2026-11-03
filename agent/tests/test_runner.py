"""Ciclo do agente: envio, buffer local e taxa de rede entre coletas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from guardian_agent.collectors.cpu import CpuSample
from guardian_agent.collectors.disk import DiskSample
from guardian_agent.collectors.memory import MemorySample
from guardian_agent.collectors.network import NetworkSample
from guardian_agent.config import AgentConfig
from guardian_agent.logging_setup import register_secret
from guardian_agent.runner import AgentRunner, CollectorSet
from guardian_agent.spool import Spool
from guardian_agent.transport import TransportError


class FakeClient:
    def __init__(self, *, fail_times: int = 0, transient: bool = True) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._fail_times = fail_times
        self._transient = transient

    def send_metrics(self, *, credential: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("metrics", payload))
        if self._fail_times > 0:
            self._fail_times -= 1
            raise TransportError("falha simulada", status=503, transient=self._transient)
        return {"recorded": True}

    def heartbeat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("heartbeat", kwargs))
        return {"status": "online"}

    def register(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("register", kwargs))
        return {"credential": "credencial-nova"}


class Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value


def collectors() -> CollectorSet:
    def networks(
        *, previous: dict[str, tuple[int, int]] | None = None,
        elapsed_seconds: float | None = None,
        exclude: tuple[str, ...] = ("lo",),
    ) -> list[NetworkSample]:
        del elapsed_seconds, exclude
        has_previous = bool(previous)
        return [
            NetworkSample(
                interface="eth0",
                rx_bytes=1000 if has_previous else 500,
                tx_bytes=2000 if has_previous else 1000,
                rx_rate_bps=10 if has_previous else None,
                tx_rate_bps=20 if has_previous else None,
            )
        ]

    return CollectorSet(
        cpu=lambda: CpuSample(percent=12.5, cores=2, load_1=0.1, load_5=0.2, load_15=0.3),
        memory=lambda: MemorySample(8000, 3000, 5000, 37.5, 0, 0, 0.0),
        disks=lambda: [DiskSample("/", "ext4", 1000, 400, 600, 40.0)],
        networks=networks,
        uptime=lambda: 3600,
        processes=lambda: 42,
    )


def build_config(tmp_path: Path, **overrides: Any) -> AgentConfig:
    data: dict[str, Any] = {
        "api_url": "https://guardian.exemplo.com",
        "server_id": "11111111-1111-4111-8111-111111111111",
        "credential": "credencial-de-teste",
        "spool_dir": str(tmp_path / "spool"),
        "state_file": str(tmp_path / "state.json"),
        "log_file": None,
    }
    data.update(overrides)
    return AgentConfig.from_dict(data)


def build_runner(
    tmp_path: Path, client: FakeClient, *, clock: Clock | None = None, **overrides: Any
) -> AgentRunner:
    config = build_config(tmp_path, **overrides)
    return AgentRunner(
        config,
        client,  # type: ignore[arg-type]
        collectors=collectors(),
        spool=Spool(config.spool_dir),
        config_path=str(tmp_path / "agent.json"),
        clock=clock or Clock(),
    )


@pytest.mark.unit
def test_tick_sends_metrics_and_heartbeat(tmp_path: Path) -> None:
    client = FakeClient()
    runner = build_runner(tmp_path, client)

    result = runner.tick()

    assert result.metrics_sent is True
    assert result.metrics_spooled is False
    assert result.heartbeat_ok is True
    assert [call[0] for call in client.calls] == ["metrics", "heartbeat"]
    assert (tmp_path / "state.json").exists()


@pytest.mark.unit
def test_payload_matches_contract(tmp_path: Path) -> None:
    client = FakeClient()
    runner = build_runner(tmp_path, client)
    runner.tick()

    payload = client.calls[0][1]
    assert payload["agent_version"]
    assert payload["host"]["cpu_percent"] == 12.5
    assert payload["host"]["ram_percent"] == 37.5
    assert payload["disks"][0]["mount_point"] == "/"
    assert payload["networks"][0]["interface"] == "eth0"
    assert payload["collected_at"].endswith("Z")


@pytest.mark.unit
def test_transient_failure_spools_payload(tmp_path: Path) -> None:
    # Falha na coleta atual e também no flush imediato.
    client = FakeClient(fail_times=2, transient=True)
    runner = build_runner(tmp_path, client)

    result = runner.tick()

    assert result.metrics_sent is False
    assert result.metrics_spooled is True
    assert result.spool_flushed == 0
    assert len(runner._spool) == 1  # noqa: SLF001 - verificação de estado interno


@pytest.mark.unit
def test_spool_is_flushed_on_next_tick(tmp_path: Path) -> None:
    client = FakeClient(fail_times=2, transient=True)
    runner = build_runner(tmp_path, client)
    runner.tick()
    assert len(runner._spool) == 1  # noqa: SLF001

    result = runner.tick()
    assert result.metrics_sent is True
    assert result.spool_flushed == 1
    assert len(runner._spool) == 0  # noqa: SLF001


@pytest.mark.unit
def test_permanent_failure_is_not_spooled(tmp_path: Path) -> None:
    client = FakeClient(fail_times=1, transient=False)
    runner = build_runner(tmp_path, client)

    result = runner.tick()

    assert result.metrics_sent is False
    assert result.metrics_spooled is False
    assert len(runner._spool) == 0  # noqa: SLF001


@pytest.mark.unit
def test_network_rate_is_computed_between_ticks(tmp_path: Path) -> None:
    client = FakeClient()
    clock = Clock()
    runner = build_runner(tmp_path, client, clock=clock)

    runner.tick()
    clock.value += 30
    runner.tick()

    second_payload = client.calls[2][1]
    assert second_payload["networks"][0]["rx_rate_bps"] == 10


@pytest.mark.unit
def test_ensure_registered_saves_credential(tmp_path: Path) -> None:
    client = FakeClient()
    config = build_config(tmp_path, credential=None, provisioning_token="t" * 40)
    runner = AgentRunner(
        config,
        client,  # type: ignore[arg-type]
        collectors=collectors(),
        spool=Spool(config.spool_dir),
        config_path=str(tmp_path / "agent.json"),
    )

    updated = runner.ensure_registered()

    assert updated.credential == "credencial-nova"
    assert updated.provisioning_token is None
    saved = (tmp_path / "agent.json").read_text(encoding="utf-8")
    assert "credencial-nova" in saved
    assert "t" * 40 not in saved


@pytest.mark.unit
def test_credit_is_redacted_in_logs() -> None:
    import logging

    from guardian_agent.logging_setup import SecretFilter

    register_secret("credencial-super-secreta")
    record = logging.LogRecord(
        name="guardian_agent",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=%s",
        args=("credencial-super-secreta",),
        exc_info=None,
    )
    assert SecretFilter().filter(record) is True
    assert "credencial-super-secreta" not in record.getMessage()
