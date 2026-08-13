import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (  # noqa: F401
    Competition,
    JobRun,
    Match,
    ModelVersion,
    Prediction,
    Season,
    Team,
)
from tests.conftest import engine


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s


@pytest.mark.asyncio
async def test_all_tables_exist(session):
    result = await session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    )
    tables = {row[0] for row in result}
    expected = {
        "competitions", "seasons", "teams", "matches", "team_match_stats",
        "odds_snapshots", "model_versions", "predictions", "prediction_outcomes",
        "parlays", "job_runs",
    }
    assert expected.issubset(tables), f"Missing: {expected - tables}"


@pytest.mark.asyncio
async def test_insert_and_select(session):
    comp = Competition(id=uuid.uuid4(), external_id="ext-001", name="Liga MX", country="Mexico")
    session.add(comp)
    await session.commit()

    result = await session.execute(
        text("SELECT name FROM competitions WHERE external_id = 'ext-001'")
    )
    assert result.fetchone()[0] == "Liga MX"


@pytest.mark.asyncio
async def test_unique_constraint(session):
    session.add(Competition(id=uuid.uuid4(), external_id="ext-uniq", name="First", country="XX"))
    await session.commit()

    session.add(Competition(id=uuid.uuid4(), external_id="ext-uniq", name="Second", country="YY"))
    with pytest.raises(Exception):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_relations(session):
    comp = Competition(id=uuid.uuid4(), external_id="rel-c", name="Liga MX", country="Mexico")
    season = Season(id=uuid.uuid4(), competition_id=comp.id, name="2026", start_date=datetime(2026, 1, 1))
    home = Team(id=uuid.uuid4(), external_id="t-home", name="Home FC")
    away = Team(id=uuid.uuid4(), external_id="t-away", name="Away FC")
    match = Match(id=uuid.uuid4(), external_id="m-001", season_id=season.id,
                  home_team_id=home.id, away_team_id=away.id,
                  kickoff_at=datetime(2026, 8, 17), status="scheduled")
    session.add_all([comp, season, home, away, match])
    await session.commit()

    result = await session.execute(
        text("SELECT ht.name FROM matches m JOIN teams ht ON m.home_team_id = ht.id WHERE m.external_id = 'm-001'")
    )
    assert result.fetchone()[0] == "Home FC"


@pytest.mark.asyncio
async def test_jobrun_idempotency(session):
    session.add(JobRun(id=uuid.uuid4(), job_type="ingest", idempotency_key="key-001"))
    await session.commit()

    session.add(JobRun(id=uuid.uuid4(), job_type="ingest", idempotency_key="key-001"))
    with pytest.raises(Exception):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_prediction(session):
    comp = Competition(id=uuid.uuid4(), external_id="p-comp", name="Liga MX", country="Mexico")
    season = Season(id=uuid.uuid4(), competition_id=comp.id, name="2026", start_date=datetime(2026, 1, 1))
    home = Team(id=uuid.uuid4(), external_id="p-home", name="Home")
    away = Team(id=uuid.uuid4(), external_id="p-away", name="Away")
    match = Match(id=uuid.uuid4(), external_id="p-match", season_id=season.id,
                  home_team_id=home.id, away_team_id=away.id,
                  kickoff_at=datetime(2026, 8, 17), status="scheduled")
    mv = ModelVersion(id=uuid.uuid4(), name="poisson", version="1.0.0",
                      feature_set_version="1.0.0", status="candidate")
    pred = Prediction(id=uuid.uuid4(), match_id=match.id, model_version_id=mv.id,
                      market="over_under_2_5", selection="over",
                      probability=0.647, fair_odds=1.545, risk_level="medium",
                      inputs_hash="abc123", prediction_timestamp=datetime(2026, 8, 17))
    session.add_all([comp, season, home, away, match, mv, pred])
    await session.commit()

    result = await session.execute(text("SELECT probability FROM predictions WHERE id = :id"), {"id": pred.id})
    assert result.fetchone()[0] == 0.647
