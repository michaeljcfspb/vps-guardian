"""Coleta de contadores e taxas de rede por interface."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psutil

MAX_INTERFACES = 32

# Mesmo contrato aceito pela central (schemas/agent.py). Um nome fora do padrão faria
# o payload inteiro ser rejeitado com 422, então filtramos na origem.
VALID_INTERFACE_NAME = re.compile(r"^[A-Za-z0-9_.:@-]{1,32}$")


@dataclass(frozen=True, slots=True)
class NetworkSample:
    interface: str
    rx_bytes: int
    tx_bytes: int
    rx_rate_bps: int | None
    tx_rate_bps: int | None


def is_excluded(interface: str, exclude: tuple[str, ...]) -> bool:
    """Exclui loopback e prefixos configurados (ex.: ``docker``, ``veth``, ``br-``)."""
    for pattern in exclude:
        if pattern and (interface == pattern or interface.startswith(pattern)):
            return True
    return False


def collect_networks(
    psutil_module: Any = psutil,
    *,
    previous: dict[str, tuple[int, int]] | None = None,
    elapsed_seconds: float | None = None,
    exclude: tuple[str, ...] = ("lo",),
    max_interfaces: int = MAX_INTERFACES,
) -> list[NetworkSample]:
    counters = psutil_module.net_io_counters(pernic=True)
    samples: list[NetworkSample] = []

    for interface, counter in sorted(counters.items()):
        if is_excluded(interface, exclude):
            continue
        if not VALID_INTERFACE_NAME.match(interface):
            # Nome não suportado pelo contrato da central (ex.: "Conexão Local* 1").
            continue

        rx = int(counter.bytes_recv)
        tx = int(counter.bytes_sent)
        rx_rate: int | None = None
        tx_rate: int | None = None

        if previous and interface in previous and elapsed_seconds and elapsed_seconds > 0:
            prev_rx, prev_tx = previous[interface]
            # Contador que diminui indica reinício/estouro: taxa não é calculável.
            if rx >= prev_rx and tx >= prev_tx:
                rx_rate = int((rx - prev_rx) * 8 / elapsed_seconds)
                tx_rate = int((tx - prev_tx) * 8 / elapsed_seconds)

        samples.append(
            NetworkSample(
                interface=interface[:32],
                rx_bytes=rx,
                tx_bytes=tx,
                rx_rate_bps=rx_rate,
                tx_rate_bps=tx_rate,
            )
        )
        if len(samples) >= max_interfaces:
            break

    return samples


def current_counters(samples: list[NetworkSample]) -> dict[str, tuple[int, int]]:
    """Estado a persistir para calcular a taxa da próxima coleta."""
    return {sample.interface: (sample.rx_bytes, sample.tx_bytes) for sample in samples}
