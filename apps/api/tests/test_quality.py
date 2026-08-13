from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Match, OddsSnapshot
from app.quality.validator import DataQualityValidator
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with session_factory() as s:
        await load_demo_seed(s)
        yield s


async def _first_match(session, scheduled: bool = False) -> Match:
    stmt = select(Match)
    if scheduled:
        stmt = stmt.where(Match.status == "scheduled")
    return (await session.execute(stmt.limit(1))).scalar_one()


def _odds(match: Match, idempotency_key: str, odds: float, observed_at=None) -> OddsSnapshot:
    observed_at = observed_at or datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
    return OddsSnapshot(
        match_id=match.id,
        provider="demo-odds",
        market="over_under_2_5",
        line=2.5,
        selection="over",
        odds=odds,
        observed_at=observed_at,
        received_at=observed_at,
        idempotency_key=idempotency_key,
    )


@pytest.mark.asyncio
async def test_reports_intentional_incomplete_cases(session):
    report = await DataQualityValidator().analyze(session)

    checks = {a.check: a for a in report.alerts}
    assert "missing_stats" in checks
    assert "match-hist-30" in checks["missing_stats"].provenance
    assert "missing_odds" in checks
    assert "match-up-12" in checks["missing_odds"].provenance


@pytest.mark.asyncio
async def test_coverage_metrics(session):
    report = await DataQualityValidator().analyze(session)

    assert report.metrics.teams == 12
    assert report.metrics.matches_historical == 30
    assert report.metrics.matches_upcoming == 12
    assert report.metrics.coverage_stats < 100
    assert report.metrics.coverage_odds < 100


@pytest.mark.asyncio
async def test_quality_is_not_probability(session):
    report = await DataQualityValidator().analyze(session)

    assert report.metric_type == "data_quality"
    assert "probability" not in [a.check for a in report.alerts]
    assert 0.0 <= report.overall_score <= 100.0


@pytest.mark.asyncio
async def test_detects_duplicate_match(session):
    await session.execute(text("DROP INDEX ix_matches_external_id"))
    await session.commit()

    first = await _first_match(session)
    dup = Match(
        external_id=first.external_id,
        season_id=first.season_id,
        home_team_id=first.home_team_id,
        away_team_id=first.away_team_id,
        kickoff_at=first.kickoff_at,
        status=first.status,
    )
    session.add(dup)
    await session.commit()

    report = await DataQualityValidator().analyze(session)
    checks = {a.check: a for a in report.alerts}
    assert "duplicate_match" in checks


@pytest.mark.asyncio
async def test_detects_invalid_odds(session):
    match = await _first_match(session, scheduled=True)
    session.add(_odds(match, idempotency_key="bad-odds-test", odds=0.9,
                      observed_at=datetime(2026, 8, 11, 8, 3, tzinfo=timezone.utc)))
    await session.commit()

    report = await DataQualityValidator().analyze(session)
    checks = {a.check: a for a in report.alerts}
    assert "invalid_odds" in checks


@pytest.mark.asyncio
async def test_detects_invalid_status(session):
    match = await _first_match(session)
    match.status = "postponed"
    await session.commit()

    report = await DataQualityValidator().analyze(session)
    checks = {a.check: a for a in report.alerts}
    assert "invalid_status" in checks


@pytest.mark.asyncio
async def test_detects_duplicate_odds_idempotency(session):
    await session.execute(text("DROP INDEX ix_odds_snapshots_idempotency_key"))
    await session.commit()

    match = await _first_match(session, scheduled=True)
    session.add(_odds(match, idempotency_key="dup-key-test", odds=1.8, observed_at=datetime(2026, 8, 11, 8, 10, tzinfo=timezone.utc)))
    session.add(_odds(match, idempotency_key="dup-key-test", odds=1.9, observed_at=datetime(2026, 8, 11, 8, 11, tzinfo=timezone.utc)))
    await session.commit()

    report = await DataQualityValidator().analyze(session)
    checks = {a.check: a for a in report.alerts}
    assert "duplicate_odds" in checks
