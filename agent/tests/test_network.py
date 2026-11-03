"""Coleta de rede: taxas, exclusão de interfaces e reinício de contadores."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from guardian_agent.collectors.network import collect_networks, current_counters, is_excluded


def make_psutil(counters: dict[str, tuple[int, int]]) -> SimpleNamespace:
    pernic = {
        name: SimpleNamespace(bytes_recv=rx, bytes_sent=tx)
        for name, (rx, tx) in counters.items()
    }
    return SimpleNamespace(net_io_counters=lambda **kwargs: pernic)


@pytest.mark.unit
def test_loopback_is_excluded_by_default() -> None:
    module = make_psutil({"lo": (10, 10), "eth0": (100, 200)})
    samples = collect_networks(module)
    assert [sample.interface for sample in samples] == ["eth0"]


@pytest.mark.unit
def test_excluded_prefixes() -> None:
    module = make_psutil({"eth0": (1, 1), "docker0": (2, 2), "veth1234": (3, 3)})
    samples = collect_networks(module, exclude=("lo", "docker", "veth"))
    assert [sample.interface for sample in samples] == ["eth0"]


@pytest.mark.unit
def test_rates_are_computed_in_bits_per_second() -> None:
    previous = {"eth0": (1000, 500)}
    module = make_psutil({"eth0": (11000, 5500)})

    samples = collect_networks(module, previous=previous, elapsed_seconds=10)
    assert samples[0].rx_rate_bps == (10000 * 8) // 10
    assert samples[0].tx_rate_bps == (5000 * 8) // 10


@pytest.mark.unit
def test_counter_reset_yields_no_rate() -> None:
    previous = {"eth0": (5000, 5000)}
    module = make_psutil({"eth0": (10, 10)})

    samples = collect_networks(module, previous=previous, elapsed_seconds=10)
    assert samples[0].rx_rate_bps is None
    assert samples[0].tx_rate_bps is None


@pytest.mark.unit
def test_first_collection_has_no_rate() -> None:
    module = make_psutil({"eth0": (10, 10)})
    samples = collect_networks(module, previous=None, elapsed_seconds=None)
    assert samples[0].rx_rate_bps is None


@pytest.mark.unit
def test_current_counters_roundtrip() -> None:
    module = make_psutil({"eth0": (10, 20), "eth1": (30, 40)})
    samples = collect_networks(module)
    assert current_counters(samples) == {"eth0": (10, 20), "eth1": (30, 40)}


@pytest.mark.unit
def test_interface_outside_contract_is_skipped() -> None:
    module = make_psutil({"eth0": (1, 1), "Conexão Local* 1": (2, 2)})
    samples = collect_networks(module)
    assert [sample.interface for sample in samples] == ["eth0"]


@pytest.mark.unit
def test_is_excluded_helpers() -> None:
    assert is_excluded("lo", ("lo",)) is True
    assert is_excluded("docker0", ("docker",)) is True
    assert is_excluded("eth0", ("docker",)) is False
    assert is_excluded("eth0", ()) is False
