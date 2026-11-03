"""Erros de aplicação e handlers HTTP padronizados.

Regra: a resposta de erro nunca revela detalhes internos (stack trace, SQL, DSN).
Detalhes técnicos vão para o log estruturado, correlacionados por ``request_id``.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class APIError(Exception):
    """Erro de negócio com código estável para o cliente."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Erro interno"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)


class BadRequestError(APIError):
    status_code = 400
    code = "bad_request"
    message = "Requisição inválida"


class UnauthorizedError(APIError):
    status_code = 401
    code = "unauthorized"
    message = "Autenticação necessária"


class ForbiddenError(APIError):
    status_code = 403
    code = "forbidden"
    message = "Acesso negado"


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"
    message = "Recurso não encontrado"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"
    message = "Conflito com o estado atual do recurso"


class PayloadTooLargeError(APIError):
    status_code = 413
    code = "payload_too_large"
    message = "Payload excede o tamanho máximo permitido"


class RateLimitedError(APIError):
    status_code = 429
    code = "rate_limited"
    message = "Muitas tentativas. Aguarde antes de tentar novamente."


class ServiceUnavailableError(APIError):
    status_code = 503
    code = "service_unavailable"
    message = "Serviço temporariamente indisponível"


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error("api_error", code=exc.code, detail=exc.message)
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Expõe apenas metadados de validação — nunca os valores recebidos."""
    fields = [
        {
            "location": ".".join(str(part) for part in error.get("loc", ())),
            "message": error.get("msg", "valor inválido"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return error_response(
        status_code=422,
        code="validation_error",
        message="Dados inválidos na requisição",
        details={"fields": fields},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_error",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
    )
    return error_response(
        status_code=500,
        code="internal_error",
        message="Erro interno do servidor",
    )
