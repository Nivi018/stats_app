"""Runner de trabajos: ejecuta handlers, persiste estado y decide retry/DLQ.

- Éxito      -> JobRun `completed`.
- Fallo determinista  -> JobRun `dlq` y el trabajo va a la DLQ (sin reintento).
- Fallo transitorio  -> reintento con backoff exponencial hasta `max_attempts`,
  luego JobRun `dlq` + DLQ.
- Entrega duplicada   -> se omite si el JobRun ya está `completed` (idempotencia).
"""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.broker import QueueBroker
from app.jobs.payload import JobEnvelope
from app.models import JobRun

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

Handler = Callable[[dict, AsyncSession], Awaitable[None]]


class DeterministicJobError(Exception):
    """Fallo determinista: no se reintenta, va directo a DLQ."""


class TransientJobError(Exception):
    """Fallo transitorio: se reintenta con backoff hasta el límite."""


class JobRunner:
    def __init__(
        self,
        broker: QueueBroker,
        session_factory,
        handlers: dict[str, Handler],
        max_attempts: int = 3,
        backoff_base: float = 0.1,
    ) -> None:
        self._broker = broker
        self._session_factory = session_factory
        self._handlers = handlers
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base

    def _backoff(self, attempt: int) -> float:
        return self._backoff_base * (2 ** (attempt - 1))

    async def process_one(self) -> str:
        await self._broker.move_due()
        envelope = await self._broker.dequeue()
        if envelope is None:
            return "empty"

        async with self._session_factory() as session:
            job_run = await self._get_or_create(session, envelope)

            if job_run.status == "completed":
                return "duplicate"

            handler = self._handlers.get(envelope.job_type)
            if handler is None:
                return await self._fail_deterministic(session, envelope, job_run, f"Handler desconocido: {envelope.job_type}")

            job_run.status = "in_progress"
            job_run.started_at = datetime.now(timezone.utc)
            job_run.attempt = envelope.attempt
            await session.commit()

            try:
                await handler(envelope.payload, session)
            except DeterministicJobError as exc:
                return await self._fail_deterministic(session, envelope, job_run, str(exc))
            except Exception as exc:  # transitorio por defecto
                return await self._fail_transient(session, envelope, job_run, str(exc))

            job_run.status = "completed"
            job_run.completed_at = datetime.now(timezone.utc)
            job_run.error_message = None
            await session.commit()
            return "processed"

    async def _get_or_create(self, session: AsyncSession, envelope: JobEnvelope) -> JobRun:
        stmt = select(JobRun).where(JobRun.idempotency_key == envelope.idempotency_key)
        job_run = (await session.execute(stmt)).scalar_one_or_none()
        if job_run is None:
            job_run = JobRun(
                job_type=envelope.job_type,
                idempotency_key=envelope.idempotency_key,
                status="pending",
                attempt=1,
                max_attempts=envelope.max_attempts,
            )
            session.add(job_run)
            await session.commit()
        return job_run

    async def _fail_deterministic(
        self, session: AsyncSession, envelope: JobEnvelope, job_run: JobRun, message: str
    ) -> str:
        job_run.status = "dlq"
        job_run.error_message = message
        job_run.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await self._broker.send_dlq(envelope)
        return "dlq"

    async def _fail_transient(
        self, session: AsyncSession, envelope: JobEnvelope, job_run: JobRun, message: str
    ) -> str:
        envelope.attempt += 1
        job_run.attempt = envelope.attempt
        if envelope.attempt > envelope.max_attempts:
            job_run.status = "dlq"
            job_run.error_message = message
            job_run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await self._broker.send_dlq(envelope)
            return "dlq"

        job_run.status = "pending"
        job_run.error_message = message
        await session.commit()
        await self._broker.requeue_with_backoff(envelope, self._backoff(envelope.attempt))
        return "retry"
