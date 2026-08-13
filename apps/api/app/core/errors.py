"""Manejo de errores canónico y correlación de requests.

Toda respuesta de error usa `ErrorDto`: `code`, `message`, `details` y
`correlation_id`, alineado con el OpenAPI canónico.
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.providers import InvalidProviderPayload
from app.schemas.matchday import ErrorDto

CORRELATION_HEADER = "X-Correlation-Id"


def get_correlation_id(request: Request) -> str:
    value = request.headers.get(CORRELATION_HEADER)
    if value:
        return value
    return request.state.correlation_id


def error_response(status_code: int, code: str, message: str, request: Request, details: dict | None = None) -> JSONResponse:
    payload = ErrorDto(
        code=code,
        message=message,
        details=details,
        correlation_id=get_correlation_id(request),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def setup_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response

    @app.exception_handler(InvalidProviderPayload)
    async def invalid_payload_handler(request: Request, exc: InvalidProviderPayload):
        return error_response(422, "invalid_payload", str(exc), request)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        return error_response(500, "internal_error", "Error interno del servidor", request)
