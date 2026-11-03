"""Rate limiting em memória (janela deslizante), conforme ADR-0006.

Limitação conhecida e documentada: o estado é local ao processo. A API deve rodar com
uma única instância/worker até existir um store compartilhado. Por isso a interface é
isolada — trocar a implementação não altera as rotas.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Conta eventos por chave dentro de uma janela deslizante."""

    def __init__(self, max_events: int, window_seconds: int, *, clock: type[time] = time) -> None:
        if max_events < 1:
            raise ValueError("max_events deve ser >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds deve ser >= 1")
        self._max_events = max_events
        self._window = float(window_seconds)
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> RateLimitResult:
        """Registra uma tentativa e informa se ela é permitida."""
        now = self._clock.monotonic()
        cutoff = now - self._window

        with self._lock:
            bucket = self._events.get(key)
            if bucket is None:
                bucket = deque()
                self._events[key] = bucket

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._max_events:
                retry_after = max(1, int(bucket[0] + self._window - now) + 1)
                return RateLimitResult(
                    allowed=False, remaining=0, retry_after_seconds=retry_after
                )

            bucket.append(now)
            return RateLimitResult(
                allowed=True,
                remaining=self._max_events - len(bucket),
                retry_after_seconds=0,
            )

    def peek(self, key: str) -> int:
        """Quantidade de eventos na janela, sem registrar novo evento."""
        now = self._clock.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._events.get(key)
            if not bucket:
                return 0
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            return len(bucket)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)

    def prune(self) -> int:
        """Remove chaves sem eventos na janela atual. Retorna quantas foram removidas."""
        now = self._clock.monotonic()
        cutoff = now - self._window
        removed = 0
        with self._lock:
            for key in list(self._events):
                bucket = self._events[key]
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    del self._events[key]
                    removed += 1
        return removed


class RateLimitRegistry:
    """Agrupa os limitadores nomeados da aplicação."""

    def __init__(self) -> None:
        self._limiters: dict[str, SlidingWindowRateLimiter] = {}
        self._lock = threading.Lock()

    def register(
        self, name: str, *, max_events: int, window_seconds: int
    ) -> SlidingWindowRateLimiter:
        with self._lock:
            limiter = self._limiters.get(name)
            if limiter is None:
                limiter = SlidingWindowRateLimiter(max_events, window_seconds)
                self._limiters[name] = limiter
            return limiter

    def get(self, name: str) -> SlidingWindowRateLimiter:
        try:
            return self._limiters[name]
        except KeyError as exc:  # pragma: no cover - erro de programação
            raise KeyError(f"Rate limiter não registrado: {name}") from exc

    def reset_all(self) -> None:
        with self._lock:
            for limiter in self._limiters.values():
                limiter.reset()
