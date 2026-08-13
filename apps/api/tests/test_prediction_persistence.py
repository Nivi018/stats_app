import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.jobs.broker import QueueBroker
from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
from app.jobs.payload import JobEnvelope
from app.jobs.runner import JobRunner
from app.main import app
from app.models import Prediction
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def broker() -> QueueBroker:
    b = QueueBroker()
    await b.flush()
    yield b
    await b.close()


@pytest_asyncio.fixture
async def runner(broker):
    async with session_factory() as session:
        await load_demo_seed(session)
    return JobRunner(
        broker=broker,
        session_factory=session_factory,
        handlers=build_handlers(session_factory),
        backoff_base=0.01,
    )


def _envelope(key: str) -> JobEnvelope:
    return JobEnvelope(job_type=COMPUTE_PREDICTION_JOB, idempotency_key=key, payload={"match_id": "match-up-01"})


@pytest.mark.asyncio
async def test_recalculation_preserves_history(runner, broker):
    await broker.enqueue(_envelope("pred-a"))
    await runner.process_one()
    await broker.enqueue(_envelope("pred-b"))
    await runner.process_one()

    async with session_factory() as session:
        predictions = (await session.execute(select(Prediction).order_by(Prediction.prediction_timestamp))).scalars().all()
        assert len(predictions) == 4  # dos cálculos: over+under cada uno
        assert predictions[0].prediction_timestamp != predictions[2].prediction_timestamp


@pytest.mark.asyncio
async def test_prediction_stores_inputs_provenance(runner, broker):
    await broker.enqueue(_envelope("pred-prov"))
    await runner.process_one()

    async with session_factory() as session:
        prediction = (await session.execute(select(Prediction).limit(1))).scalar_one()
        inputs = json.loads(prediction.inputs)
        assert "lambda_home" in inputs
        assert "lambda_away" in inputs
        assert inputs["model_version"] == "1.0.0"
        assert inputs["dataset"] == "demo-2026-apertura"
        assert prediction.inputs_hash


@pytest.mark.asyncio
async def test_transaction_avoids_partial_publish(runner, broker):
    """Un fallo a mitad de un lote no publica predicciones parciales."""
    from app.jobs.runner import DeterministicJobError
    from app.models import Match, ModelVersion

    async def partial_fail_handler(payload, session):
        async with session_factory() as s:
            match = (await s.execute(select(Match).limit(1))).scalar_one()
            mv = (await s.execute(select(ModelVersion).limit(1))).scalar_one_or_none()
            if mv is None:
                mv = ModelVersion(
                    name="poisson", version="1.0.0", status="candidate",
                    feature_set_version="1.0.0", activated_at=datetime.now(timezone.utc),
                )
                s.add(mv)
                await s.flush()
            now = datetime.now(timezone.utc)
            s.add(Prediction(
                match_id=match.id,
                model_version_id=mv.id,
                market="over_under_2_5",
                selection="over",
                probability=0.5,
                fair_odds=2.0,
                data_quality="medium",
                risk_level="medium",
                inputs_hash="partial",
                prediction_timestamp=now,
            ))
            raise DeterministicJobError("fallo a mitad del lote")

    runner._handlers["partial_fail"] = partial_fail_handler
    await broker.enqueue(JobEnvelope(job_type="partial_fail", idempotency_key="pred-partial"))
    outcome = await runner.process_one()

    assert outcome == "dlq"
    async with session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(Prediction))).scalar()
        assert count == 0


# --- API por ID ---


@pytest.mark.asyncio
async def test_api_returns_prediction_by_id(runner, broker):
    await broker.enqueue(_envelope("pred-api"))
    await runner.process_one()

    async with session_factory() as session:
        prediction = (await session.execute(select(Prediction).limit(1))).scalar_one()
        prediction_id = str(prediction.id)

    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/predictions/{prediction_id}")
    app.state.session_factory = None

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == prediction_id
    assert data["selection"] in {"over", "under"}
    assert 0 < data["probability"] < 1
    assert data["inputs_hash"]
    assert data["model_version_id"]


@pytest.mark.asyncio
async def test_api_prediction_not_found(runner, broker):
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/predictions/{uuid.uuid4()}")
    app.state.session_factory = None

    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "not_found"
    assert data["correlation_id"]
