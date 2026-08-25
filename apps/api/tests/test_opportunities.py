from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.opportunities import OpportunityService
from app.jobs.broker import QueueBroker
from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
from app.jobs.payload import JobEnvelope
from app.jobs.runner import JobRunner
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with session_factory() as s:
        await load_demo_seed(s)
        yield s


@pytest_asyncio.fixture
async def computed(session):
    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(broker=broker, session_factory=session_factory, handlers=build_handlers(session_factory))
    # Calcular predicciones para los próximos partidos.
    for i in range(1, 13):
        await broker.enqueue(JobEnvelope(
            job_type=COMPUTE_PREDICTION_JOB,
            idempotency_key=f"scan-{i}",
            payload={"match_id": f"match-up-{i:02d}"},
        ))
        await runner.process_one()
    await broker.close()


# Momento de evaluación: justo tras el snapshot de cuotas del seed (11/08 08:00).
AT = datetime(2026, 8, 11, 8, 5, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_opportunities_return_signal_rows(computed):
    service = OpportunityService(session_factory)
    opportunities = await service.get_opportunities(at=AT)

    assert opportunities, "debería haber oportunidades"
    for o in opportunities:
        assert o.market == "over_under_2_5"
        assert o.selection in {"over", "under"}
        assert 0 < o.model_probability < 1
        assert o.observed_odds > 1.0
        assert o.edge_pp != 0 or o.ev != 0
        assert o.data_quality in {"high", "medium", "low"}
        assert o.risk_level in {"low", "medium", "high"}
        assert o.snapshot_age_minutes >= 0


@pytest.mark.asyncio
async def test_opportunities_include_confidence(computed):
    service = OpportunityService(session_factory)
    opportunities = await service.get_opportunities(at=AT)

    assert opportunities
    for o in opportunities:
        assert o.confidence_level in {"baja", "media", "alta"}
        assert 0 <= o.confidence_score <= 100
        assert o.confidence_factors


@pytest.mark.asyncio
async def test_opportunities_sorted_signals_first(computed):
    service = OpportunityService(session_factory)
    opportunities = await service.get_opportunities(at=AT)

    seen_non_signal = False
    for o in opportunities:
        if o.is_signal:
            assert seen_non_signal is False, "señales deben ir primero"
        else:
            seen_non_signal = True


@pytest.mark.asyncio
async def test_opportunities_edge_ev_consistency(computed):
    service = OpportunityService(session_factory)
    opportunities = await service.get_opportunities(at=AT)

    for o in opportunities:
        # EV esperado: p_modelo * cuota_observada - 1
        assert o.ev == pytest.approx(o.model_probability * o.observed_odds - 1, abs=1e-3)


@pytest.mark.asyncio
async def test_no_predictions_returns_empty(session):
    service = OpportunityService(session_factory)
    opportunities = await service.get_opportunities(at=AT)
    assert opportunities == []


@pytest.mark.asyncio
async def test_filter_by_min_edge(computed):
    service = OpportunityService(session_factory)
    all_op = await service.get_opportunities(at=AT, min_edge=-100)
    none_op = await service.get_opportunities(at=AT, min_edge=9999)

    assert all_op
    assert none_op == []
    assert all(o.edge_pp >= -100 for o in all_op)


@pytest.mark.asyncio
async def test_filter_by_risk(computed):
    service = OpportunityService(session_factory)
    low_risk = await service.get_opportunities(at=AT, risk="low")

    assert all(o.risk_level == "low" for o in low_risk)


@pytest.mark.asyncio
async def test_filter_by_matchday(computed):
    service = OpportunityService(session_factory)
    jornada_1 = await service.get_opportunities(at=AT, matchday=1)
    jornada_99 = await service.get_opportunities(at=AT, matchday=99)

    assert jornada_1
    assert jornada_99 == []


@pytest.mark.asyncio
async def test_sort_is_deterministic(computed):
    service = OpportunityService(session_factory)
    a = await service.get_opportunities(at=AT, sort="edge")
    b = await service.get_opportunities(at=AT, sort="edge")

    assert a == b
    edges = [o.edge_pp for o in a]
    assert edges == sorted(edges, reverse=True) or any(o.is_signal for o in a)


@pytest.mark.asyncio
async def test_sort_by_ev(computed):
    service = OpportunityService(session_factory)
    by_ev = await service.get_opportunities(at=AT, sort="ev")

    evs = [o.ev for o in by_ev if not o.is_signal]
    signals = [o for o in by_ev if o.is_signal]
    assert signals or evs
    if len(evs) >= 2:
        assert evs == sorted(evs, reverse=True)
