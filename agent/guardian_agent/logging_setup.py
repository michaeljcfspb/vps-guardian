"""Logs do agente: JSON em arquivo com rotação + stderr (journald).

Além de nunca registrar segredos por construção, há uma rede de segurança: valores
registrados via :func:`register_secret` são mascarados em qualquer mensagem.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from typing import Any

_SECRETS: set[str] = set()
_STANDARD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName",
    }
)


def register_secret(value: str | None) -> None:
    if value and len(value) >= 8:
        _SECRETS.add(value)


class SecretFilter(logging.Filter):
    """Substitui segredos conhecidos por ``***`` antes da formatação."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not _SECRETS:
            return True
        message = record.getMessage()
        redacted = message
        for secret in _SECRETS:
            if secret in redacted:
                redacted = redacted.replace(secret, "***")
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)[:2000]
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    level: str = "INFO", log_file: str | None = None, *, stderr: bool = True
) -> logging.Logger:
    """Configura o logger raiz do agente (idempotente)."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = JsonFormatter()
    secret_filter = SecretFilter()

    if stderr:
        stream = logging.StreamHandler(stream=sys.stderr)
        stream.setFormatter(formatter)
        stream.addFilter(secret_filter)
        root.addHandler(stream)

    if log_file:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover - depende de permissão no host
            logging.getLogger("guardian_agent").warning(
                "não foi possível abrir o log em arquivo: %s", type(exc).__name__
            )
        else:
            file_handler.setFormatter(formatter)
            file_handler.addFilter(secret_filter)
            root.addHandler(file_handler)

    return logging.getLogger("guardian_agent")
