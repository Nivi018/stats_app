"""Pruebas de las señales destacadas (US6)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def computed():
    from app.jobs.broker import QueueBroker
    from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
    from app.jobs.payload import JobEnvelope
    from app.jobs.runner import JobRunner

    async with session_factory() as session:
        await load_demo_seed(session)

    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(broker=broker, session_factory=session_factory, handlers=build_handlers(session_factory))
    for i in range(1, 13):
        match_id = f"match-up-{i:02d}"
        await broker.enqueue(JobEnvelope(job_type=COMPUTE_PREDICTION_JOB, idempotency_key=f"sig-{match_id}", payload={"match_id": match_id}))
        await runner.process_one()
    await broker.close()


async def _freshen_odds() -> None:
    from app.jobs.freshen_demo_odds import freshen_demo_market

    await freshen_demo_market(session_factory)


@pytest_asyncio.fixture
async def client(computed):
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.session_factory = None


@pytest.mark.asyncio
async def test_signals_featured_solo_senales_y_con_limite(client):
    await _freshen_odds()

    response = await client.get("/api/v1/signals/featured?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 3
    assert all(o["is_signal"] is True for o in data)


@pytest.mark.asyncio
async def test_signals_featured_ordenadas_por_edge(client):
    await _freshen_odds()

    response = await client.get("/api/v1/signals/featured?limit=10")
    data = response.json()
    assert any(o["is_signal"] for o in data)
    edges = [o["edge_pp"] for o in data if o["is_signal"]]
    assert edges == sorted(edges, reverse=True)


@pytest.mark.asyncio
async def test_signals_featured_incluye_confianza(client):
    await _freshen_odds()

    response = await client.get("/api/v1/signals/featured?limit=5")
    data = response.json()
    assert data, "se esperaban señales con cuotas frescas"
    for o in data:
        assert o["confidence_level"] in {"alta", "media", "baja"}
        assert 0 <= o["confidence_score"] <= 100
        assert o["confidence_factors"]


@pytest.mark.asyncio
async def test_signals_featured_vacio_sin_cuotas_frescas(client):
    # Sin refrescar: las cuotas del seed están viejas -> sin oportunidades -> sin señales.
    response = await client.get("/api/v1/signals/featured?limit=3")
    assert response.status_code == 200
    assert response.json() == []
