"""Coletores: CPU, memória, disco, uptime e contagem de processos."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from guardian_agent.collectors.cpu import clamp_percent, collect_cpu
from guardian_agent.collectors.disk import PSEUDO_FILESYSTEMS, collect_disks
from guardian_agent.collectors.memory import collect_memory
from guardian_agent.collectors.system import (
    collect_process_count,
    collect_uptime_seconds,
    read_os_release,
)


def fake_psutil(**overrides: Any) -> SimpleNamespace:
    base = {
        "cpu_percent": lambda interval: 42.75,
        "cpu_count": lambda logical=True: 4,
        "virtual_memory": lambda: SimpleNamespace(
            total=8000, used=3000, available=5000, percent=37.5
        ),
        "swap_memory": lambda: SimpleNamespace(total=2000, used=500, percent=25.0),
        "disk_partitions": lambda all=False: [
            SimpleNamespace(device="/dev/sda1", mountpoint="/", fstype="ext4"),
            SimpleNamespace(device="proc", mountpoint="/proc", fstype="proc"),
            SimpleNamespace(device="/dev/sdb1", mountpoint="/data", fstype="xfs"),
        ],
        "disk_usage": lambda path: SimpleNamespace(total=1000, used=400, free=600),
        "boot_time": lambda: 1000.0,
        "pids": lambda: [1, 2, 3],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
def test_cpu_sample_is_collected() -> None:
    sample = collect_cpu(fake_psutil(), sample_interval=0)
    assert sample.percent == 42.75
    assert sample.cores == 4
    assert sample.load_1 >= 0


@pytest.mark.unit
def test_cpu_percent_is_clamped() -> None:
    assert clamp_percent(150) == 100.0
    assert clamp_percent(-5) == 0.0
    assert clamp_percent(42.756) == 42.76


@pytest.mark.unit
def test_memory_sample_consistency() -> None:
    memory = collect_memory(fake_psutil())
    assert memory.total_bytes == 8000
    assert memory.used_bytes <= memory.total_bytes
    assert memory.available_bytes <= memory.total_bytes
    assert memory.swap_used_bytes <= memory.swap_total_bytes


@pytest.mark.unit
def test_memory_is_clamped_when_inconsistent() -> None:
    module = fake_psutil(
        virtual_memory=lambda: SimpleNamespace(total=100, used=500, available=500, percent=120.0),
        swap_memory=lambda: SimpleNamespace(total=10, used=50, percent=130.0),
    )
    memory = collect_memory(module)
    assert memory.used_bytes == 100
    assert memory.available_bytes == 100
    assert memory.swap_used_bytes == 10
    assert memory.percent == 100.0


@pytest.mark.unit
def test_disks_exclude_pseudo_filesystems() -> None:
    disks = collect_disks(fake_psutil())
    assert [disk.mount_point for disk in disks] == ["/", "/data"]


@pytest.mark.unit
def test_disk_percent_is_computed() -> None:
    disks = collect_disks(fake_psutil())
    assert disks[0].used_percent == 40.0
    assert disks[0].filesystem == "ext4"


@pytest.mark.unit
def test_inaccessible_mount_is_skipped() -> None:
    def disk_usage(path: str) -> Any:
        if path == "/data":
            raise PermissionError
        return SimpleNamespace(total=1000, used=100, free=900)

    disks = collect_disks(fake_psutil(disk_usage=disk_usage))
    assert [disk.mount_point for disk in disks] == ["/"]


@pytest.mark.unit
def test_pseudo_filesystem_list_contains_expected_entries() -> None:
    assert "proc" in PSEUDO_FILESYSTEMS
    assert "sysfs" in PSEUDO_FILESYSTEMS
    assert "ext4" not in PSEUDO_FILESYSTEMS


@pytest.mark.unit
def test_uptime_is_computed_from_boot_time() -> None:
    assert collect_uptime_seconds(fake_psutil(), now=4600.0) == 3600


@pytest.mark.unit
def test_process_count() -> None:
    assert collect_process_count(fake_psutil()) == 3


@pytest.mark.unit
def test_process_count_failure_returns_none() -> None:
    module = fake_psutil(pids=lambda: (_ for _ in ()).throw(OSError()))
    assert collect_process_count(module) is None


@pytest.mark.unit
def test_read_os_release_parses_quotes(tmp_path) -> None:
    path = tmp_path / "os-release"
    path.write_text(
        'NAME="Ubuntu"\nVERSION_ID="24.04"\n# comentário\nID=ubuntu\n', encoding="utf-8"
    )
    data = read_os_release(path)
    assert data["NAME"] == "Ubuntu"
    assert data["VERSION_ID"] == "24.04"
    assert "comentário" not in data


@pytest.mark.unit
def test_read_os_release_missing_file(tmp_path) -> None:
    assert read_os_release(tmp_path / "nao-existe") == {}
