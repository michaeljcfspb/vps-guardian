"""Coleta de CPU, load average e núcleos."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import psutil


@dataclass(frozen=True, slots=True)
class CpuSample:
    percent: float
    cores: int
    load_1: float
    load_5: float
    load_15: float


def load_average() -> tuple[float, float, float]:
    """Load average de 1/5/15 minutos; ``(0,0,0)`` onde não há suporte (ex.: Windows)."""
    try:
        one, five, fifteen = os.getloadavg()
    except (AttributeError, OSError):
        return (0.0, 0.0, 0.0)
    return (round(one, 3), round(five, 3), round(fifteen, 3))


def collect_cpu(
    psutil_module: Any = psutil, *, sample_interval: float = 0.2
) -> CpuSample:
    percent = float(psutil_module.cpu_percent(interval=sample_interval))
    cores = int(psutil_module.cpu_count(logical=True) or 1)
    one, five, fifteen = load_average()
    return CpuSample(
        percent=clamp_percent(percent),
        cores=max(1, cores),
        load_1=one,
        load_5=five,
        load_15=fifteen,
    )


def clamp_percent(value: float) -> float:
    """Arredonda e limita a 0..100 — o schema da central rejeita fora dessa faixa."""
    return round(max(0.0, min(100.0, float(value))), 2)
