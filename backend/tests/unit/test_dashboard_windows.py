"""Configuração das janelas de série temporal (validação sem banco)."""

from __future__ import annotations

import pytest

from app.services.dashboard import WINDOWS


@pytest.mark.unit
def test_windows_are_ordered_and_bounded() -> None:
    expected = {
        "1h": 60,
        "6h": 180,
        "24h": 900,
        "7d": 3600,
    }
    assert {name: step for name, (_span, step) in WINDOWS.items()} == expected


@pytest.mark.unit
def test_each_window_has_at_most_about_170_points() -> None:
    for name, (span, step) in WINDOWS.items():
        points = span.total_seconds() / step
        assert points <= 170, name
        assert points >= 24, name
