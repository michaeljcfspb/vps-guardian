"""Coleta de memória RAM e swap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psutil

from guardian_agent.collectors.cpu import clamp_percent


@dataclass(frozen=True, slots=True)
class MemorySample:
    total_bytes: int
    used_bytes: int
    available_bytes: int
    percent: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_percent: float


def collect_memory(psutil_module: Any = psutil) -> MemorySample:
    memory = psutil_module.virtual_memory()
    swap = psutil_module.swap_memory()

    total = int(memory.total)
    used = int(memory.used)
    available = int(memory.available)

    # Garante consistência exigida pelo contrato (used/available <= total).
    used = min(used, total)
    available = min(available, total)

    swap_total = int(swap.total)
    swap_used = min(int(swap.used), swap_total)

    return MemorySample(
        total_bytes=total,
        used_bytes=used,
        available_bytes=available,
        percent=clamp_percent(memory.percent),
        swap_total_bytes=swap_total,
        swap_used_bytes=swap_used,
        swap_percent=clamp_percent(swap.percent),
    )
