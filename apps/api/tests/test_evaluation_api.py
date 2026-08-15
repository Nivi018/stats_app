"""Pruebas de métricas e historial (US5/US6) vía API."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded_session() -> AsyncSession:
    async with session_factory() as session:
        await load_demo_seed(session)
        yield session


@pytest_asyncio.fixture
async def resolved(client, seeded_session):
    """Deja predicciones calculadas y resueltas para partidos históricos."""
    from sqlalchemy import select

    from app.jobs.broker import QueueBroker
    from app.jobs.handlers import (
        COMPUTE_PREDICTION_JOB,
        RESOLVE_PREDICTION_JOB,
        build_handlers,
    )
    from app.jobs.payload import JobEnvelope
    from app.jobs.runner import JobRunner
    from app.models import Match, Prediction

    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(broker=broker, session_factory=session_factory, handlers=build_handlers(session_factory))

    for i in range(1, 31):
        match_id = f"match-hist-{i:02d}"
        await broker.enqueue(JobEnvelope(job_type=COMPUTE_PREDICTION_JOB, idempotency_key=f"ev-{match_id}", payload={"match_id": match_id}))
        await runner.process_one()

    async with session_factory() as session:
        resolvable = list((await session.execute(
            select(Match.external_id).join(Prediction, Prediction.match_id == Match.id).where(Match.status == "finished").distinct()
        )).scalars().all())

    for match_id in resolvable:
        await broker.enqueue(JobEnvelope(job_type=RESOLVE_PREDICTION_JOB, idempotency_key=f"ev-resolve-{match_id}", payload={"match_id": match_id}))
        await runner.process_one()
    await broker.close()
    return len(resolvable)


@pytest_asyncio.fixture
async def client():
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.session_factory = None


@pytest.mark.asyncio
async def test_metrics_report(resolved, client):
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()

    assert data["sample_size"] > 0
    assert data["wins"] + data["losses"] == data["sample_size"]
    assert data["hit_rate"] is not None
    assert data["brier"] is not None
    assert data["unit_roi"] is not None
    assert data["sample_sufficient"] is False or data["sample_sufficient"] is True
    assert len(data["calibration_bins"]) == 4


@pytest.mark.asyncio
async def test_metrics_filtered_by_model_version(resolved, client):
    from sqlalchemy import select

    from app.model.baseline import MODEL_NAME, MODEL_VERSION
    from app.models import ModelVersion

    async with session_factory() as session:
        mv = (await session.execute(select(ModelVersion).where(ModelVersion.name == MODEL_NAME, ModelVersion.version == MODEL_VERSION))).scalar_one()

    response = await client.get(f"/api/v1/metrics?model_version_id={mv.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["model_version_id"] == str(mv.id)
    assert data["sample_size"] > 0


@pytest.mark.asyncio
async def test_metrics_empty_when_no_outcomes(client):
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["sample_size"] == 0
    assert data["hit_rate"] is None
    assert data["sample_sufficient"] is False


@pytest.mark.asyncio
async def test_history_paginates_and_filters(resolved, client):
    response = await client.get("/api/v1/history?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) <= 5
    assert data["total"] > 0
    assert data["total_pages"] >= 1
    assert all(i["result"] in {"win", "loss", "void"} for i in data["items"])
    assert all(i["model_version"] for i in data["items"])


@pytest.mark.asyncio
async def test_history_filter_by_result(resolved, client):
    response = await client.get("/api/v1/history?result=win")
    data = response.json()
    assert data["total"] >= 0
    assert all(i["result"] == "win" for i in data["items"])


@pytest.mark.asyncio
async def test_history_filter_by_model_version(resolved, client):
    from app.model.baseline import MODEL_VERSION

    response = await client.get(f"/api/v1/history?model_version={MODEL_VERSION}")
    assert response.status_code == 200
    data = response.json()
    assert all(i["model_version"] == MODEL_VERSION for i in data["items"])
