"""Fila local (spool) de métricas."""

from __future__ import annotations

from pathlib import Path

import pytest

from guardian_agent.spool import Spool


class Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value


@pytest.mark.unit
def test_enqueue_and_read(tmp_path: Path) -> None:
    clock = Clock()
    spool = Spool(tmp_path, clock=clock)
    path = spool.enqueue({"a": 1})

    assert path.exists()
    assert len(spool) == 1
    assert spool.read(path) == {"a": 1}


@pytest.mark.unit
def test_pending_is_ordered_oldest_first(tmp_path: Path) -> None:
    clock = Clock()
    spool = Spool(tmp_path, clock=clock)
    first = spool.enqueue({"n": 1})
    clock.value += 1
    second = spool.enqueue({"n": 2})

    assert spool.pending() == [first, second]


@pytest.mark.unit
def test_ack_removes_file(tmp_path: Path) -> None:
    spool = Spool(tmp_path)
    path = spool.enqueue({"a": 1})
    spool.ack(path)
    assert len(spool) == 0
    spool.ack(path)  # idempotente


@pytest.mark.unit
def test_trim_keeps_only_max_items(tmp_path: Path) -> None:
    clock = Clock()
    spool = Spool(tmp_path, max_items=3, clock=clock)
    for index in range(5):
        spool.enqueue({"n": index})
        clock.value += 1

    pending = spool.pending()
    assert len(pending) == 3
    # Os mais antigos foram descartados: sobram os de n=2,3,4.
    assert [spool.read(p)["n"] for p in pending] == [2, 3, 4]


@pytest.mark.unit
def test_prune_removes_expired_items(tmp_path: Path) -> None:
    clock = Clock()
    spool = Spool(tmp_path, max_age_seconds=60, clock=clock)
    spool.enqueue({"n": 1})

    clock.value += 61
    assert spool.prune() == 1
    assert len(spool) == 0


@pytest.mark.unit
def test_corrupted_file_is_discarded(tmp_path: Path) -> None:
    spool = Spool(tmp_path)
    broken = tmp_path / "0000000000001-broken.json"
    broken.write_text("{invalido", encoding="utf-8")

    assert spool.read(broken) is None
    assert not broken.exists()


@pytest.mark.unit
def test_clear_removes_everything(tmp_path: Path) -> None:
    spool = Spool(tmp_path)
    for index in range(4):
        spool.enqueue({"n": index})
    assert spool.clear() == 4
    assert len(spool) == 0
