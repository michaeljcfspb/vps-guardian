"""Estado local entre coletas (contadores de rede para calcular taxas)."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class NetworkState:
    timestamp: float
    counters: dict[str, tuple[int, int]]


def load_state(path: str | Path) -> NetworkState | None:
    state_path = Path(path)
    try:
        raw = state_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    timestamp = data.get("timestamp")
    counters = data.get("counters")
    if not isinstance(timestamp, (int, float)) or not isinstance(counters, dict):
        return None

    parsed: dict[str, tuple[int, int]] = {}
    for interface, value in counters.items():
        if (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and all(isinstance(item, int) for item in value)
        ):
            parsed[str(interface)] = (int(value[0]), int(value[1]))
    return NetworkState(timestamp=float(timestamp), counters=parsed)


def save_state(path: str | Path, *, timestamp: float, counters: dict[str, tuple[int, int]]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "timestamp": timestamp,
        "counters": {name: [rx, tx] for name, (rx, tx) in counters.items()},
    }

    descriptor, temporary = tempfile.mkstemp(dir=str(state_path.parent), prefix=".state-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, state_path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
