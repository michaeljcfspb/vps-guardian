"""Aplicação FastAPI: middlewares, handlers de erro e montagem das rotas."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.errors import (
    APIError,
    api_error_handler,
    error_response,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine

MAX_BODY_BYTES = 1024 * 1024  # 1 MiB — limite de payload (PRD §9.4)
REQUEST_ID_HEADER = "X-Request-Id"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    logger = get_logger("app.guardian")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "startup",
            environment=settings.app_env,
            version=settings.deployment_version,
        )
        yield
        dispose_engine()
        logger.info("shutdown")

    application = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.deployment_version,
        description=(
            "API central de monitoramento de servidores VPS. "
            "Autenticação do painel: sessão em cookie. Autenticação de agente: Bearer."
        ),
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    application.state.settings = settings

    # CORS restrito: vazio por padrão; same-origin não precisa de CORS (PRD §11).
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-CSRF-Token", "Authorization", REQUEST_ID_HEADER],
            expose_headers=[REQUEST_ID_HEADER],
            max_age=600,
        )

    application.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(
        RequestValidationError, validation_error_handler  # type: ignore[arg-type]
    )
    application.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore[arg-type]

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        declared_length = request.headers.get("content-length")
        if declared_length and declared_length.isdigit() and int(declared_length) > MAX_BODY_BYTES:
            return error_response(
                status_code=413,
                code="payload_too_large",
                message="Payload excede o tamanho máximo permitido",
            )

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
        )
        return response

    application.include_router(health_router)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app()
