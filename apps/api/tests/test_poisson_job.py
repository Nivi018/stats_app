import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.jobs.broker import QueueBroker
from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
from app.jobs.payload import JobEnvelope
from app.jobs.runner import JobRunner
from app.model.baseline import MODEL_NAME, MODEL_VERSION
from app.models import JobRun, ModelVersion, Prediction
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
async def seeded():
    async with session_factory() as session:
        await load_demo_seed(session)


@pytest_asyncio.fixture
async def runner(broker, seeded):
    return JobRunner(
        broker=broker,
        session_factory=session_factory,
        handlers=build_handlers(session_factory),
        backoff_base=0.01,
    )


def _predict_envelope(match_id: str, key: str) -> JobEnvelope:
    return JobEnvelope(
        job_type=COMPUTE_PREDICTION_JOB,
        idempotency_key=key,
        payload={"match_id": match_id},
    )


@pytest.mark.asyncio
async def test_compute_prediction_job_persists_pair(runner, broker):
    await broker.enqueue(_predict_envelope("match-up-01", "pred-1"))
    outcome = await runner.process_one()

    assert outcome == "processed"
    async with session_factory() as session:
        predictions = (await session.execute(select(Prediction))).scalars().all()
        # Over/Under 2.5 + mercados derivados (1X2, totales por equipo, hándicap).
        assert len(predictions) >= 2
        assert {p.selection for p in predictions if p.market == "over_under_2_5"} == {"over", "under"}
        assert any(p.market == "1x2" for p in predictions)
        assert all(p.inputs_hash for p in predictions)
        assert all(0 < p.probability < 1 for p in predictions)


@pytest.mark.asyncio
async def test_double_delivery_is_idempotent(runner, broker):
    await broker.enqueue(_predict_envelope("match-up-01", "pred-dup"))
    assert await runner.process_one() == "processed"
    async with session_factory() as session:
        count_after_first = (
            await session.execute(select(func.count()).select_from(Prediction))
        ).scalar()
    await runner.process_one()  # entrega duplicada

    async with session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(Prediction))).scalar()
        assert count == count_after_first  # no se duplican

        job_run = (await session.execute(
            select(JobRun).where(JobRun.idempotency_key == "pred-dup")
        )).scalar_one()
        assert job_run.status == "completed"


@pytest.mark.asyncio
async def test_missing_match_is_deterministic_no_partial_publish(runner, broker):
    await broker.enqueue(_predict_envelope("match-no-existe", "pred-bad"))
    outcome = await runner.process_one()

    assert outcome == "dlq"
    async with session_factory() as session:
        # Ninguna predicción parcial publicada.
        count = (await session.execute(select(func.count()).select_from(Prediction))).scalar()
        assert count == 0
        job_run = (await session.execute(
            select(JobRun).where(JobRun.idempotency_key == "pred-bad")
        )).scalar_one()
        assert job_run.status == "dlq"
        assert "no encontrado" in job_run.error_message


@pytest.mark.asyncio
async def test_predictions_reference_model_version(runner, broker):
    await broker.enqueue(_predict_envelope("match-up-01", "pred-mv"))
    await runner.process_one()

    async with session_factory() as session:
        mv = (await session.execute(
            select(ModelVersion).where(ModelVersion.name == MODEL_NAME, ModelVersion.version == MODEL_VERSION)
        )).scalar_one()
        preds = (await session.execute(select(Prediction))).scalars().all()
        assert all(p.model_version_id == mv.id for p in preds)
