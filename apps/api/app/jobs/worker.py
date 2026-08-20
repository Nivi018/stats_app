"""Bucle del worker: consume la cola y enlaza observabilidad (US7).

Cada trabajo se procesa con su `correlation_id` y se registra el `job_id`
(JobRun persistido) junto al resultado. Además se registran métricas de cola.
"""

import asyncio
import sys
import time

from sqlalchemy import select

from app.core.logging import logger, reset_context, set_correlation_id, set_job_id
from app.db.session import async_session
from app.jobs.broker import QueueBroker
from app.jobs.handlers import build_handlers
from app.jobs.runner import JobRunner
from app.models import JobRun

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _job_run_id(idempotency_key: str, session_factory=None) -> str | None:
    if session_factory is None:
        session_factory = async_session
    async with session_factory() as session:
        job_run = (
            await session.execute(
                select(JobRun).where(JobRun.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        return str(job_run.id) if job_run is not None else None


async def process_next(
    broker: QueueBroker,
    runner: JobRunner,
    *,
    session_factory=None,
) -> str:
    """Procesa un trabajo del frente de la cola con contexto de observabilidad.

    Devuelve el outcome (`empty`, `processed`, `duplicate`, `retry`, `dlq`).
    """
    envelope = await broker.peek()
    if envelope is None:
        return "empty"

    set_correlation_id(envelope.correlation_id)
    try:
        outcome = await runner.process_one()
    finally:
        reset_context()
    job_id = await _job_run_id(envelope.idempotency_key, session_factory)
    set_job_id(job_id)
    logger.info(
        "job_finished",
        extra={
            "job_type": envelope.job_type,
            "idempotency_key": envelope.idempotency_key,
            "job_id": job_id,
            "outcome": outcome,
        },
    )
    reset_context()
    return outcome


async def process_forever(*, interval: float = 0.5, stats_every: float = 30.0) -> None:
    broker = QueueBroker()
    runner = JobRunner(
        broker=broker,
        session_factory=async_session,
        handlers=build_handlers(async_session),
    )
    logger.info("worker_started")
    last_stats = time.monotonic()

    while True:
        outcome = await process_next(broker, runner)
        if outcome == "empty":
            await asyncio.sleep(interval)
            continue

        now = time.monotonic()
        if now - last_stats >= stats_every:
            last_stats = now
            await _log_queue_stats(broker)


async def _log_queue_stats(broker: QueueBroker) -> None:
    backlog = await broker.work_count()
    retry = await broker.retry_count()
    dlq = await broker.dlq_count()
    logger.info(
        "queue_stats",
        extra={
            "queue_backlog": backlog,
            "queue_retry": retry,
            "queue_dlq": dlq,
        },
    )


async def run() -> None:
    try:
        await process_forever()
    except asyncio.CancelledError:
        logger.info("worker_stopped")
        raise


if __name__ == "__main__":
    asyncio.run(run())
