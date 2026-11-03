"""Informações do sistema: uptime, processos e identidade do host.

Nenhum dado sensível é lido: apenas ``/etc/os-release`` (público), kernel e arquitetura.
Variáveis de ambiente, ``.env``, chaves privadas e conteúdo de volumes nunca são lidos.
"""

from __future__ import annotations

import platform
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

OS_RELEASE_PATH = Path("/etc/os-release")


@dataclass(frozen=True, slots=True)
class SystemInfo:
    hostname: str
    os_name: str | None
    os_version: str | None
    kernel: str | None
    architecture: str | None


def collect_uptime_seconds(
    psutil_module: Any = psutil, *, now: float | None = None
) -> int:
    current = time.time() if now is None else now
    try:
        boot_time = float(psutil_module.boot_time())
    except (AttributeError, OSError, ValueError):
        return 0
    return max(0, int(current - boot_time))


def collect_process_count(psutil_module: Any = psutil) -> int | None:
    try:
        return len(psutil_module.pids())
    except (AttributeError, OSError):  # pragma: no cover - defensivo
        return None


def read_os_release(path: Path = OS_RELEASE_PATH) -> dict[str, str]:
    """Lê ``/etc/os-release`` no formato ``CHAVE="valor"``."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    result: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def collect_system_info() -> SystemInfo:
    release = read_os_release()
    try:
        hostname = socket.gethostname()
    except OSError:  # pragma: no cover - defensivo
        hostname = "desconhecido"

    return SystemInfo(
        hostname=hostname[:255],
        os_name=(release.get("NAME") or platform.system() or None),
        os_version=(release.get("VERSION_ID") or None),
        kernel=(platform.release() or None),
        architecture=(platform.machine() or None),
    )
