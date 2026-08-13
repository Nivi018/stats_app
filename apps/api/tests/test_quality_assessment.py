from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.quality.assessment import (
    QualityInputs,
    RiskInputs,
    assess_data_quality,
    assess_risk,
)
from app.quality.gather import gather_match_quality_inputs
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)

T0 = datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)


def test_quality_separated_from_probability():
    assessment = assess_data_quality(QualityInputs())
    assert assessment.metric_type == "data_quality"
    assert assessment.is_probability is False
    assert "confidence" not in assessment.factors


def test_quality_perfect_inputs_is_high():
    assessment = assess_data_quality(QualityInputs())
    assert assessment.score == 100.0
    assert assessment.level == "high"


def test_quality_degrades_with_freshness():
    fresh = assess_data_quality(QualityInputs(freshness_seconds=0))
    stale = assess_data_quality(QualityInputs(freshness_seconds=90 * 60))  # 90 min
    assert stale.score < fresh.score
    assert any("antigüedad" in f for f in stale.factors)


def test_quality_penalizes_missing_sides_and_overround():
    base = assess_data_quality(QualityInputs())
    incomplete = assess_data_quality(
        QualityInputs(has_both_odds=False, has_both_stats=False, overround_value=1.45)
    )
    assert incomplete.score < base.score
    assert any("lados del mercado" in f for f in incomplete.factors)


def test_quality_coverage_and_completeness_lower_score():
    partial = assess_data_quality(QualityInputs(coverage_ratio=0.5, completeness_ratio=0.5))
    assert partial.score == pytest.approx(75.0)


def test_risk_separated_and_not_probability():
    assessment = assess_risk(RiskInputs())
    assert assessment.metric_type == "risk"
    assert assessment.is_probability is False


def test_risk_low_with_good_sample_and_quality():
    assessment = assess_risk(RiskInputs(sample_size_total=12, sample_size_context=6, quality_score=100))
    assert assessment.level == "low"
    assert assessment.score < 40


def test_risk_high_with_small_sample():
    assessment = assess_risk(RiskInputs(sample_size_total=2, sample_size_context=0, quality_score=40))
    assert assessment.level == "high"
    assert any("Muestra reducida" in f for f in assessment.factors)


def test_risk_medium_with_moderate_sample_and_lower_quality():
    assessment = assess_risk(RiskInputs(sample_size_total=7, sample_size_context=3, quality_score=40))
    assert assessment.level == "medium"


@pytest.mark.asyncio
async def test_gather_returns_quality_for_complete_match():
    # Las cuotas demo tienen observed_at el 11/08; evaluar 5 min después.
    fresh_at = datetime(2026, 8, 11, 8, 5, tzinfo=timezone.utc)
    async with session_factory() as session:
        await load_demo_seed(session)
        inputs = await gather_match_quality_inputs(session, "match-up-01", fresh_at)

    assert inputs is not None
    assert inputs.has_both_odds is True
    assert inputs.has_both_stats is False  # upcoming no tienen stats aún
    assessment = assess_data_quality(inputs)
    assert assessment.metric_type == "data_quality"


@pytest.mark.asyncio
async def test_gather_none_for_missing_match():
    async with session_factory() as session:
        await load_demo_seed(session)
        inputs = await gather_match_quality_inputs(session, "match-no-existe", T0)
    assert inputs is None
