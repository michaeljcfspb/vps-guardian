"""Logging estruturado (JSON) com redação de campos sensíveis.

Requisitos: PRD §11 e §17.2.7 — segredos nunca podem aparecer em logs. A redação é
aplicada como *processor* do structlog e vale também para logs da stdlib, porque ambos
passam pelo mesmo formatter.
"""

from __future__ import annotations

import logging
from typing import Any, Final

import structlog

from app.core.config import Settings

REDACTED: Final = "***redacted***"
MAX_DEPTH: Final = 6

_SENSITIVE_MARKERS: Final = (
    "password",
    "senha",
    "token",
    "secret",
    "authorization",
    "cookie",
    "csrf",
    "credential",
    "credential_hash",
    "api_key",
    "apikey",
    "private_key",
    "database_url",
    "dsn",
)


def _is_sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in _SENSITIVE_MARKERS)


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Substitui valores de chaves sensíveis, recursivamente e com limite de profundidade."""
    if _depth > MAX_DEPTH:
        return REDACTED
    if isinstance(value, dict):
        return {
            key: (REDACTED if _is_sensitive_key(key) else redact(item, _depth=_depth + 1))
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item, _depth=_depth + 1) for item in value]
    return value


def redact_processor(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor do structlog: redige o evento inteiro antes da renderização."""
    result = redact(event_dict)
    return result if isinstance(result, dict) else {"event": str(result)}


def configure_logging(settings: Settings) -> None:
    """Configura structlog + stdlib com renderização JSON (ou colorida em dev)."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_processor,
    ]

    renderer: Any
    if settings.log_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # Evita duplicação e ruído de bibliotecas de terceiros.
    for name in ("uvicorn", "uvicorn.error", "sqlalchemy.engine", "httpx"):
        logging.getLogger(name).handlers = [handler]
        logging.getLogger(name).propagate = False
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.db_echo else logging.WARNING
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)
