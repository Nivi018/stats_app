"""Pruebas end-to-end del reporte de backtesting (US7)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.backtest.report import BacktestReport, run_backtest
from app.backtest.run import load_match_records
from app.backtest.walk_forward import walk_forward_splits
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def records():
    async with session_factory() as session:
        await load_demo_seed(session)
        return await load_match_records(session)


@pytest.mark.asyncio
async def test_backtest_report_structure_and_baselines(records):
    report = await run_backtest(session_factory, records, n_folds=4)

    assert isinstance(report, BacktestReport)
    assert report.n_folds == 4
    assert len(report.folds) == 4
    assert [b.name for b in report.overall] == ["market", "league", "poisson"]
    assert [b.name for b in report.out_of_sample] == ["market", "league", "poisson"]
    assert [b.name for b in report.final_holdout] == ["market", "league", "poisson"]


@pytest.mark.asyncio
async def test_backtest_folds_cumulative_train(records):
    folds = walk_forward_splits(records, 4)
    assert len(folds) == 4
    seen = 0
    for fold in folds:
        assert fold.train_size == seen
        seen += fold.test_size
    assert seen == len(records)


@pytest.mark.asyncio
async def test_backtest_coverage_and_metrics(records):
    report = await run_backtest(session_factory, records, n_folds=4)

    for baseline in report.overall:
        assert 0.0 <= baseline.coverage <= 1.0
        assert baseline.metrics.sample_size == baseline.coverage_n
        # Con cuotas en todos los partidos históricos, mercado cubre todo.
        assert baseline.metrics.brier is not None or baseline.coverage_n == 0


@pytest.mark.asyncio
async def test_backtest_deterministic(records):
    a = await run_backtest(session_factory, records, n_folds=4, random_seed=42)
    b = await run_backtest(session_factory, records, n_folds=4, random_seed=42)
    assert a.to_dict() == b.to_dict()


@pytest.mark.asyncio
async def test_backtest_market_has_full_coverage(records):
    report = await run_backtest(session_factory, records, n_folds=4)
    market = next(b for b in report.overall if b.name == "market")
    assert market.coverage == pytest.approx(1.0)
    assert market.coverage_n > 0


@pytest.mark.asyncio
async def test_backtest_final_holdout_excluded_from_out_of_sample(records):
    report = await run_backtest(session_factory, records, n_folds=4)
    poisson_oos = next(b for b in report.out_of_sample if b.name == "poisson")
    poisson_hold = next(b for b in report.final_holdout if b.name == "poisson")
    assert poisson_oos.coverage_n + poisson_hold.coverage_n <= poisson_oos.candidates_n + poisson_hold.candidates_n


@pytest.mark.asyncio
async def test_backtest_report_serializes_to_dict(records):
    report = await run_backtest(session_factory, records, n_folds=4)
    payload = report.to_dict()
    assert payload["n_folds"] == 4
    assert "out_of_sample" in payload
    assert "final_holdout" in payload
    assert len(payload["folds"]) == 4
