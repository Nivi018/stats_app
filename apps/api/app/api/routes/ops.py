"""Endpoints de operación (observabilidad) bajo `/api/v1`."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app.core.metrics import registry
from app.jobs.broker import QueueBroker
from app.models import OddsSnapshot

router = APIRouter()


@router.get("/ops/metrics", response_class=PlainTextResponse)
async def ops_metrics(request: Request) -> PlainTextResponse:
    broker = QueueBroker()
    try:
        backlog = await broker.work_count()
        retry = await broker.retry_count()
        dlq = await broker.dlq_count()
    finally:
        await broker.close()
    factory = getattr(request.app.state, "session_factory", None)
    freshness = await _latest_snapshot_freshness(factory)
    return PlainTextResponse(
        registry.render(
            queue_backlog=backlog,
            queue_retry=retry,
            queue_dlq=dlq,
            odds_freshness_seconds=freshness,
        ),
        media_type="text/plain; version=0.0.4",
    )


async def _latest_snapshot_freshness(session_factory=None) -> int | None:
    if session_factory is None:
        from app.db.session import async_session

        session_factory = async_session

    async with session_factory() as session:
        latest = (
            await session.execute(
                select(OddsSnapshot.observed_at).order_by(OddsSnapshot.observed_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if latest is None:
            return None
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - latest).total_seconds()))
