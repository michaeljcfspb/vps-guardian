"""Fila local limitada (spool) para sobreviver a quedas de comunicação.

Cada item é um arquivo JSON com nome ordenável (timestamp em ms). Escrita atômica,
leitura tolerante a arquivo corrompido (descartado) e limite duplo: quantidade e
idade. Quando o limite é atingido, o item mais antigo é descartado — métrica antiga
tem menos valor que a atual.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any


class Spool:
    def __init__(
        self,
        directory: str | Path,
        *,
        max_items: int = 120,
        max_age_seconds: int = 21600,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if max_items < 1:
            raise ValueError("max_items deve ser >= 1")
        if max_age_seconds < 1:
            raise ValueError("max_age_seconds deve ser >= 1")
        self._dir = Path(directory)
        self._max_items = max_items
        self._max_age = max_age_seconds
        self._clock = clock
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def directory(self) -> Path:
        return self._dir

    def __len__(self) -> int:
        return len(self._files())

    def enqueue(self, payload: dict[str, Any]) -> Path:
        stamp = int(self._clock() * 1000)
        name = f"{stamp:013d}-{uuid.uuid4().hex[:12]}.json"
        target = self._dir / name
        temporary = self._dir / f".tmp-{name}"

        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)

        self.trim()
        return target

    def pending(self) -> list[Path]:
        """Arquivos pendentes, do mais antigo para o mais novo."""
        return self._files()

    def read(self, path: Path) -> dict[str, Any] | None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self.ack(path)
            return None
        if not isinstance(data, dict):
            self.ack(path)
            return None
        return data

    def ack(self, path: Path) -> None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()

    def prune(self) -> int:
        """Remove itens mais antigos que o limite de idade. Retorna quantos saíram."""
        cutoff = self._clock() - self._max_age
        removed = 0
        for path in self._files():
            if self._stamp(path) < cutoff:
                self.ack(path)
                removed += 1
        return removed

    def trim(self) -> int:
        """Mantém no máximo ``max_items`` (descarta os mais antigos)."""
        files = self._files()
        excess = len(files) - self._max_items
        removed = 0
        for path in files[: max(0, excess)]:
            self.ack(path)
            removed += 1
        return removed

    def clear(self) -> int:
        removed = 0
        for path in self._files():
            self.ack(path)
            removed += 1
        return removed

    def _files(self) -> list[Path]:
        try:
            entries = [p for p in self._dir.iterdir() if p.suffix == ".json"]
        except FileNotFoundError:
            return []
        return sorted(entries, key=lambda p: p.name)

    @staticmethod
    def _stamp(path: Path) -> float:
        prefix = path.name.split("-", 1)[0]
        try:
            return int(prefix) / 1000.0
        except ValueError:
            return 0.0
