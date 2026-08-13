import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.jobs.broker import QueueBroker
from app.jobs.handlers import INGEST_DEMO_JOB, build_handlers
from app.jobs.payload import JobEnvelope
from app.jobs.runner import DeterministicJobError, JobRunner, TransientJobError
from app.models import JobRun, Match, Team
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
    return JobRunner(
        broker=broker,
        session_factory=session_factory,
        handlers=build_handlers(),
        backoff_base=0.01,
    )


def _ingest_envelope(key: str = "seed-1", payload: dict | None = None) -> JobEnvelope:
    return JobEnvelope(
        job_type=INGEST_DEMO_JOB,
        idempotency_key=key,
        payload=payload if payload is not None else {"version": "1.0.0"},
    )


async def _jobrun_by_key(session: AsyncSession, key: str) -> JobRun | None:
    stmt = select(JobRun).where(JobRun.idempotency_key == key)
    return (await session.execute(stmt)).scalar_one_or_none()


@pytest.mark.asyncio
async def test_process_ingest_job_seeds_and_completes(runner, broker):
    await broker.enqueue(_ingest_envelope())
    outcome = await runner.process_one()

    assert outcome == "processed"
    async with session_factory() as session:
        teams = (await session.execute(select(func.count()).select_from(Team))).scalar()
        matches = (await session.execute(select(func.count()).select_from(Match))).scalar()
        job_run = await _jobrun_by_key(session, "seed-1")
        assert teams == 12
        assert matches == 42
        assert job_run.status == "completed"
        assert job_run.attempt == 1


@pytest.mark.asyncio
async def test_double_delivery_does_not_change_counts(runner, broker):
    async with session_factory() as session:
        await runner.process_one()  # noop
    await broker.enqueue(_ingest_envelope())

    await runner.process_one()
    await runner.process_one()  # entrega duplicada

    async with session_factory() as session:
        teams = (await session.execute(select(func.count()).select_from(Team))).scalar()
        matches = (await session.execute(select(func.count()).select_from(Match))).scalar()
        completed = (await session.execute(
            select(func.count()).select_from(JobRun).where(JobRun.status == "completed")
        )).scalar()
        assert teams == 12
        assert matches == 42
        assert completed == 1


@pytest.mark.asyncio
async def test_deterministic_failure_goes_to_dlq(runner, broker):
    async def bad_handler(payload, session):
        raise DeterministicJobError("proveedor devolvió datos inválidos")

    runner._handlers[INGEST_DEMO_JOB] = bad_handler
    await broker.enqueue(_ingest_envelope("seed-bad"))
    outcome = await runner.process_one()

    assert outcome == "dlq"
    assert await broker.dlq_count() == 1
    async with session_factory() as session:
        job_run = await _jobrun_by_key(session, "seed-bad")
        assert job_run.status == "dlq"
        assert "inválidos" in job_run.error_message


@pytest.mark.asyncio
async def test_transient_failure_retries_then_dlq(runner, broker):
    calls = {"n": 0}

    async def flaky_handler(payload, session):
        calls["n"] += 1
        raise TransientJobError("timeout de proveedor")

    runner._handlers[INGEST_DEMO_JOB] = flaky_handler
    runner._max_attempts = 3
    await broker.enqueue(_ingest_envelope("seed-flaky"))

    await runner.process_one()
    await broker.move_due(now=10**12)  # forzar vencimiento de backoff
    await runner.process_one()
    await broker.move_due(now=10**12)
    outcome = await runner.process_one()

    assert calls["n"] == 3
    assert outcome == "dlq"
    assert await broker.dlq_count() == 1
    async with session_factory() as session:
        job_run = await _jobrun_by_key(session, "seed-flaky")
        assert job_run.status == "dlq"
        assert job_run.attempt == 4  # intentos acumulados hasta superar el límite


@pytest.mark.asyncio
async def test_transient_failure_succeeds_on_retry(runner, broker):
    calls = {"n": 0}

    async def eventually_ok(payload, session):
        calls["n"] += 1
        if calls["n"] < 2:
            raise TransientJobError("aún no listo")
        from app.seeds.loader import load_demo_seed

        await load_demo_seed(session)

    runner._handlers[INGEST_DEMO_JOB] = eventually_ok
    await broker.enqueue(_ingest_envelope("seed-retry-ok"))

    assert await runner.process_one() == "retry"
    await broker.move_due(now=10**12)
    outcome = await runner.process_one()

    assert outcome == "processed"
    assert calls["n"] == 2
    async with session_factory() as session:
        job_run = await _jobrun_by_key(session, "seed-retry-ok")
        assert job_run.status == "completed"
        assert job_run.attempt == 2


@pytest.mark.asyncio
async def test_invalid_payload_is_deterministic_failure(runner, broker):
    await broker.enqueue(_ingest_envelope("seed-noversion", payload={}))
    outcome = await runner.process_one()

    assert outcome == "dlq"
    assert await broker.dlq_count() == 1
    async with session_factory() as session:
        job_run = await _jobrun_by_key(session, "seed-noversion")
        assert job_run.status == "dlq"
        assert "version" in job_run.error_message
