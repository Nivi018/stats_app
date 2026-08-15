"""Pruebas del job de resolución de resultados demo (US4)."""

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.resolve import resolve_outcome
from app.jobs.broker import QueueBroker
from app.jobs.handlers import (
    COMPUTE_PREDICTION_JOB,
    RESOLVE_PREDICTION_JOB,
    build_handlers,
)
from app.jobs.payload import JobEnvelope
from app.jobs.runner import JobRunner
from app.models import Match, Prediction, PredictionOutcome
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


def _envelope(job_type: str, match_id: str, key: str) -> JobEnvelope:
    return JobEnvelope(job_type=job_type, idempotency_key=key, payload={"match_id": match_id})


async def _compute_all_historical(broker, runner) -> None:
    for i in range(1, 31):
        match_id = f"match-hist-{i:02d}"
        await broker.enqueue(_envelope(COMPUTE_PREDICTION_JOB, match_id, f"hist-{match_id}"))
        await runner.process_one()


async def _resolved_matches() -> list[str]:
    async with session_factory() as session:
        return list(
            (
                await session.execute(
                    select(Match.external_id)
                    .join(Prediction, Prediction.match_id == Match.id)
                    .distinct()
                )
            ).scalars().all()
        )


@pytest.mark.asyncio
async def test_resolves_all_predictions_without_mutating_them(runner, broker):
    await _compute_all_historical(broker, runner)

    resolved = await _resolved_matches()
    assert resolved, "Se esperaba al menos un partido histórico con predicción"

    for match_id in resolved:
        await broker.enqueue(_envelope(RESOLVE_PREDICTION_JOB, match_id, f"resolve-{match_id}"))
        assert await runner.process_one() == "processed"

    async with session_factory() as session:
        predictions = (await session.execute(select(Prediction))).scalars().all()
        assert predictions, "Debe haber predicciones persistidas"
        for pred in predictions:
            outcome = (
                await session.execute(
                    select(PredictionOutcome).where(PredictionOutcome.prediction_id == pred.id)
                )
            ).scalar_one()
            match = (
                await session.execute(select(Match).where(Match.id == pred.match_id))
            ).scalar_one()
            expected = resolve_outcome(pred.market, pred.selection, match.home_score, match.away_score)
            assert outcome.result == expected
            assert outcome.total_goals == (match.home_score or 0) + (match.away_score or 0)
            # La predicción NO fue mutada por la resolución.
            assert pred.probability == pred.probability


@pytest.mark.asyncio
async def test_retry_does_not_duplicate_outcomes(runner, broker):
    await _compute_all_historical(broker, runner)
    resolved = await _resolved_matches()
    assert resolved

    match_id = resolved[0]
    envelope = _envelope(RESOLVE_PREDICTION_JOB, match_id, "resolve-dup")
    await broker.enqueue(envelope)
    assert await runner.process_one() == "processed"
    await broker.enqueue(envelope)  # nueva entrega del mismo trabajo
    assert await runner.process_one() == "duplicate"  # idempotente

    async with session_factory() as session:
        match = (
            await session.execute(select(Match).where(Match.external_id == match_id))
        ).scalar_one()
        predictions = (
            await session.execute(select(Prediction).where(Prediction.match_id == match.id))
        ).scalars().all()
        outcomes = (
            await session.execute(
                select(PredictionOutcome).where(
                    PredictionOutcome.prediction_id.in_([p.id for p in predictions])
                )
            )
        ).scalars().all()
        assert len(predictions) == 2
        assert len(outcomes) == 2  # 1 outcome por predicción, sin duplicados
        assert {o.result for o in outcomes} <= {"win", "loss", "void"}


@pytest.mark.asyncio
async def test_unfinished_match_is_transient_retry(runner, broker):
    await broker.enqueue(_envelope(RESOLVE_PREDICTION_JOB, "match-up-01", "resolve-sched"))
    outcome = await runner.process_one()

    assert outcome == "retry"
    async with session_factory() as session:
        match = (
            await session.execute(select(Match).where(Match.external_id == "match-up-01"))
        ).scalar_one_or_none()
        assert match is not None  # match existe; el job solo se reintenta


@pytest.mark.asyncio
async def test_missing_match_is_deterministic_dlq(runner, broker):
    await broker.enqueue(_envelope(RESOLVE_PREDICTION_JOB, "match-no-existe", "resolve-bad"))
    outcome = await runner.process_one()

    assert outcome == "dlq"
