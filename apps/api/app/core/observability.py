"""Middleware de observabilidad: métricas y log estructurado por request (US7)."""

import time

from app.core.logging import logger
from app.core.metrics import registry


async def request_observability_middleware(request, call_next):
    method = request.method
    path = request.url.path
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        registry.record_request(method, path, 500, duration_ms)
        logger.error(
            "request_error",
            exc_info=True,
            extra={
                "method": method,
                "path": path,
                "status": 500,
                "duration_ms": round(duration_ms, 2),
            },
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    registry.record_request(method, path, response.status_code, duration_ms)
    logger.info(
        "request",
        extra={
            "method": method,
            "path": path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response
