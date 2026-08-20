"""Pruebas de rendimiento: lecturas críticas sin N+1 y métricas registradas (US3)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded():
    async with session_factory() as session:
        await load_demo_seed(session)


class QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def _before_cursor_execute(self, *args, **kwargs) -> None:
        self.count += 1


def _install_counter() -> QueryCounter:
    counter = QueryCounter()
    event.listen(engine.sync_engine, "before_cursor_execute", counter._before_cursor_execute)
    return counter


def _remove_counter(counter: QueryCounter) -> None:
    event.remove(engine.sync_engine, "before_cursor_execute", counter._before_cursor_execute)


async def _compute_predictions():
    from app.jobs.broker import QueueBroker
    from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
    from app.jobs.payload import JobEnvelope
    from app.jobs.runner import JobRunner

    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(broker=broker, session_factory=session_factory, handlers=build_handlers(session_factory))
    for i in range(1, 13):
        match_id = f"match-up-{i:02d}"
        await broker.enqueue(JobEnvelope(job_type=COMPUTE_PREDICTION_JOB, idempotency_key=f"perf-{match_id}", payload={"match_id": match_id}))
        await runner.process_one()
    await broker.close()


@pytest.mark.asyncio
async def test_matchday_current_sin_n_plus_one(seeded):
    counter = _install_counter()
    try:
        app.state.session_factory = session_factory
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/matchdays/current")
    finally:
        app.state.session_factory = None
        _remove_counter(counter)

    assert response.status_code == 200
    assert len(response.json()["matches"]) == 12
    # 1 (partidos+equipos) + 1 (cuotas por lote) => sin N+1 por partido.
    assert counter.count <= 4, f"Posible N+1: {counter.count} consultas"


@pytest.mark.asyncio
async def test_opportunities_sin_n_plus_one(seeded):
    from datetime import datetime, timezone

    from app.application.opportunities import OpportunityService

    await _compute_predictions()

    counter = _install_counter()
    try:
        service = OpportunityService(session_factory)
        # Momento de evaluación justo tras el snapshot del seed (11/08 08:00).
        opportunities = await service.get_opportunities(
            at=datetime(2026, 8, 11, 8, 5, tzinfo=timezone.utc)
        )
    finally:
        _remove_counter(counter)

    assert opportunities, "debería haber oportunidades"
    # 1 (partidos) + 1 (predicciones) + 1 (snapshots) => sin N+1 por partido.
    assert counter.count <= 5, f"Posible N+1: {counter.count} consultas"


@pytest.mark.asyncio
async def test_metrics_sin_n_plus_one(seeded):
    from app.jobs.broker import QueueBroker
    from app.jobs.handlers import COMPUTE_PREDICTION_JOB, RESOLVE_PREDICTION_JOB, build_handlers
    from app.jobs.payload import JobEnvelope
    from app.jobs.runner import JobRunner
    from sqlalchemy import select

    from app.models import Match, Prediction

    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(broker=broker, session_factory=session_factory, handlers=build_handlers(session_factory))
    for i in range(1, 31):
        match_id = f"match-hist-{i:02d}"
        await broker.enqueue(JobEnvelope(job_type=COMPUTE_PREDICTION_JOB, idempotency_key=f"perf-{match_id}", payload={"match_id": match_id}))
        await runner.process_one()

    async with session_factory() as session:
        resolvable = list((await session.execute(
            select(Match.external_id).join(Prediction, Prediction.match_id == Match.id).where(Match.status == "finished").distinct()
        )).scalars().all())
    for match_id in resolvable:
        await broker.enqueue(JobEnvelope(job_type=RESOLVE_PREDICTION_JOB, idempotency_key=f"perf-res-{match_id}", payload={"match_id": match_id}))
        await runner.process_one()
    await broker.close()

    counter = _install_counter()
    try:
        app.state.session_factory = session_factory
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/metrics")
    finally:
        app.state.session_factory = None
        _remove_counter(counter)

    assert response.status_code == 200
    assert response.json()["sample_size"] > 0
    # 1 (outcomes+predicciones) + 1 (snapshots por lote) => sin N+1 por predicción.
    assert counter.count <= 4, f"Posible N+1: {counter.count} consultas"
