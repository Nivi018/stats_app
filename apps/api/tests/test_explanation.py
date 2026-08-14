import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.explanation.builder import build_explanation
from app.jobs.broker import QueueBroker
from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
from app.jobs.payload import JobEnvelope
from app.jobs.runner import JobRunner
from app.models import Prediction
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)

FORBIDDEN = ("garantiz", "asegurad", "seguro", "dinero fácil", "pick ganador")


def _any_forbidden(text: str) -> bool:
    return any(word in text.lower() for word in FORBIDDEN)


@pytest_asyncio.fixture
async def prediction() -> Prediction:
    async with session_factory() as session:
        await load_demo_seed(session)
    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(broker=broker, session_factory=session_factory, handlers=build_handlers(session_factory))
    await broker.enqueue(JobEnvelope(
        job_type=COMPUTE_PREDICTION_JOB,
        idempotency_key="expl-1",
        payload={"match_id": "match-up-01"},
    ))
    await runner.process_one()
    await broker.close()

    async with session_factory() as session:
        return (await session.execute(select(Prediction).where(Prediction.selection == "over"))).scalar_one()


def test_explanation_derived_from_persisted_inputs(prediction):
    explanation = build_explanation(prediction)

    assert explanation["is_guarantee"] is False
    assert explanation["model_version"] == "1.0.0"
    assert explanation["provenance"]["inputs_hash"] == prediction.inputs_hash
    assert explanation["provenance"]["dataset"] == "demo-2026-apertura"
    assert explanation["prediction_timestamp"]


def test_explanation_includes_factors_risks_and_formula(prediction):
    explanation = build_explanation(prediction)

    assert explanation["factors"]
    assert any("goles esperados" in f for f in explanation["factors"])
    assert explanation["risks"]
    assert "Poisson" in explanation["formula"]
    assert "cuota justa" in explanation["summary"]


def test_explanation_no_guarantee_language(prediction):
    explanation = build_explanation(prediction)

    joined = " ".join([
        explanation["summary"],
        *explanation["factors"],
        *explanation["risks"],
        explanation["formula"],
    ])
    assert _any_forbidden(joined) is False


def test_explanation_deterministic(prediction):
    a = build_explanation(prediction)
    b = build_explanation(prediction)
    assert a == b


def test_explanation_reflects_probability(prediction):
    explanation = build_explanation(prediction)
    expected_pct = f"{prediction.probability * 100:.1f}%"
    assert expected_pct in explanation["summary"]
    assert json.dumps(explanation, ensure_ascii=False)
