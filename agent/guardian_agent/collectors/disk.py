"""Coleta de uso de disco por ponto de montagem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psutil

from guardian_agent.collectors.cpu import clamp_percent

# Sistemas de arquivos que não representam armazenamento real do host.
PSEUDO_FILESYSTEMS = frozenset(
    {
        "autofs",
        "binfmt_misc",
        "cgroup",
        "cgroup2",
        "configfs",
        "debugfs",
        "devpts",
        "devtmpfs",
        "fusectl",
        "hugetlbfs",
        "mqueue",
        "nsfs",
        "proc",
        "pstore",
        "rpc_pipefs",
        "securityfs",
        "squashfs",
        "sysfs",
        "tracefs",
    }
)

# Teto de pontos de montagem por coleta (o schema da central aceita até 64).
MAX_MOUNTS = 64


@dataclass(frozen=True, slots=True)
class DiskSample:
    mount_point: str
    filesystem: str | None
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float


def collect_disks(
    psutil_module: Any = psutil, *, max_mounts: int = MAX_MOUNTS
) -> list[DiskSample]:
    samples: list[DiskSample] = []
    seen: set[str] = set()

    for partition in psutil_module.disk_partitions(all=False):
        if partition.fstype in PSEUDO_FILESYSTEMS:
            continue
        mount_point = str(partition.mountpoint)
        if mount_point in seen:
            continue
        try:
            usage = psutil_module.disk_usage(mount_point)
        except (PermissionError, OSError):
            # Ponto de montagem inacessível para o usuário do serviço: ignorar.
            continue

        total = int(usage.total)
        used = int(usage.used)
        free = int(usage.free)
        if total <= 0:
            continue

        seen.add(mount_point)
        samples.append(
            DiskSample(
                mount_point=mount_point[:255],
                filesystem=(partition.fstype or None),
                total_bytes=total,
                used_bytes=min(used, total),
                free_bytes=min(free, total),
                used_percent=clamp_percent(used / total * 100),
            )
        )
        if len(samples) >= max_mounts:
            break

    samples.sort(key=lambda item: item.mount_point)
    return samples
