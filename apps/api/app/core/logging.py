"""Logging estructurado JSON con contexto distribuido (US7).

Cada entrada incluye `service`, `release` y, cuando existe, `correlation_id`
(solicitud) y `job_id` (ejecución de trabajo). Nunca se registran secretos.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from app.core.config import settings

SERVICE_NAME = "stats-api"

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)

_EXTRA_FIELDS = (
    "method",
    "path",
    "status",
    "duration_ms",
    "outcome",
    "job_type",
    "idempotency_key",
    "queue_backlog",
    "queue_retry",
    "queue_dlq",
)


def set_correlation_id(value: str | None) -> None:
    """Ancla el id de correlación al contexto de la ejecución actual."""
    if value:
        _correlation_id.set(value)


def set_job_id(value: str | None) -> None:
    if value:
        _job_id.set(value)


def reset_context() -> None:
    _correlation_id.set(None)
    _job_id.set(None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": SERVICE_NAME,
            "release": settings.VERSION,
            "message": record.getMessage(),
        }
        correlation_id = _correlation_id.get()
        if correlation_id:
            payload["correlation_id"] = correlation_id
        job_id = _job_id.get()
        if job_id:
            payload["job_id"] = job_id
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(service: str = SERVICE_NAME) -> None:
    """Configura el logger raíz para emitir JSON a stdout."""
    global SERVICE_NAME
    SERVICE_NAME = service
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


logger = logging.getLogger("stats")
