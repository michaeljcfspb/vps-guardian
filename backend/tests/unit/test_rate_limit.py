"""Testes de unidade do rate limiter em memória."""

from __future__ import annotations

import pytest

from app.core.rate_limit import RateLimitRegistry, SlidingWindowRateLimiter


class FakeClock:
    """Relógio controlável para testar janelas sem sleep."""

    def __init__(self) -> None:
        self.current = 1000.0

    def monotonic(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


@pytest.mark.unit
def test_allows_up_to_limit_then_blocks() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(3, 60, clock=clock)  # type: ignore[arg-type]

    for _ in range(3):
        assert limiter.check("ip:1").allowed is True

    blocked = limiter.check("ip:1")
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after_seconds >= 1


@pytest.mark.unit
def test_window_slides_and_allows_again() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(2, 60, clock=clock)  # type: ignore[arg-type]

    assert limiter.check("k").allowed
    assert limiter.check("k").allowed
    assert not limiter.check("k").allowed

    clock.advance(61)
    assert limiter.check("k").allowed is True


@pytest.mark.unit
def test_keys_are_independent() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(1, 60, clock=clock)  # type: ignore[arg-type]

    assert limiter.check("a").allowed
    assert limiter.check("b").allowed
    assert not limiter.check("a").allowed


@pytest.mark.unit
def test_peek_does_not_consume() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(2, 60, clock=clock)  # type: ignore[arg-type]

    limiter.check("k")
    assert limiter.peek("k") == 1
    assert limiter.peek("k") == 1
    assert limiter.check("k").allowed


@pytest.mark.unit
def test_reset_clears_key() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(1, 60, clock=clock)  # type: ignore[arg-type]
    assert limiter.check("k").allowed
    assert not limiter.check("k").allowed

    limiter.reset("k")
    assert limiter.check("k").allowed


@pytest.mark.unit
def test_prune_removes_stale_keys() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(5, 30, clock=clock)  # type: ignore[arg-type]
    limiter.check("old")
    clock.advance(31)
    assert limiter.prune() == 1
    assert limiter.peek("old") == 0


@pytest.mark.unit
def test_invalid_arguments_are_rejected() -> None:
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(0, 10)
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(1, 0)


@pytest.mark.unit
def test_registry_returns_same_instance() -> None:
    registry = RateLimitRegistry()
    first = registry.register("login", max_events=5, window_seconds=60)
    second = registry.register("login", max_events=99, window_seconds=1)
    assert first is second


@pytest.mark.unit
def test_registry_unknown_limiter_raises() -> None:
    with pytest.raises(KeyError):
        RateLimitRegistry().get("inexistente")
