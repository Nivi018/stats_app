from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.features.feature_set import FeatureSet, FeatureVector, LAMBDA_CLAMP, MIN_TOTAL_FOR_PREDICTION
from app.models import Competition, Match, ModelVersion, OddsSnapshot, Prediction, Season, Team, TeamMatchStats
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)

# Momento de predicción: mucho después del último partido histórico del seed.
TS = datetime(2026, 8, 30, 20, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with session_factory() as s:
        await load_demo_seed(s)
        yield s


@pytest.mark.asyncio
async def test_features_computed_for_known_team(session):
    fv = await FeatureSet().compute(session, "match-up-01", TS)

    assert fv is not None
    assert fv.version == "1.0.0"
    assert fv.feature_set_hash
    assert fv.sample_size_total >= MIN_TOTAL_FOR_PREDICTION
    assert fv.lambda_home > 0 and fv.lambda_away > 0
    assert 0.05 <= fv.lambda_home <= 5.0
    assert 0.05 <= fv.lambda_away <= 5.0


@pytest.mark.asyncio
async def test_excludes_future_matches(session):
    # Antes del primer histórico no debería haber features (sin muestra previa).
    early = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    fv = await FeatureSet().compute(session, "match-up-01", early)
    # match-up-01 es el 3/08; los históricos son 2/07+; en 1/07 no hay nada.
    assert fv is None or fv.sample_size_total == 0 or fv.sample_size_total < MIN_TOTAL_FOR_PREDICTION


@pytest.mark.asyncio
async def test_feature_vector_has_no_odds_fields(session):
    fv = await FeatureSet().compute(session, "match-up-01", TS)
    fields = fv.__dataclass_fields__
    assert not any("odds" in name or "cuota" in name for name in fields)
    assert "lambda_home" in fields


@pytest.mark.asyncio
async def test_new_team_uses_prior_and_low_quality(session):
    # Equipo nuevo sin histórico: debe quedar con calidad baja o sin predicción.
    comp = (await session.execute(select(Competition).where(Competition.external_id == "demo-liga-mx"))).scalar_one()
    season = (await session.execute(select(Season).where(Season.competition_id == comp.id))).scalar_one()
    new_team = Team(external_id="mx-new", name="Nuevo FC", short_name="NUE")
    known = (await session.execute(select(Team).where(Team.external_id == "mx-ame"))).scalar_one()
    session.add(new_team)
    await session.flush()
    match = Match(
        external_id="match-up-new",
        season_id=season.id,
        home_team_id=new_team.id,
        away_team_id=known.id,
        kickoff_at=datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc),
        status="scheduled",
    )
    session.add(match)
    await session.commit()

    fv = await FeatureSet().compute(session, "match-up-new", TS)
    assert fv is not None  # el equipo conocido da muestra; el nuevo usa prior
    assert fv.data_quality == "low"


@pytest.mark.asyncio
async def test_deterministic_across_calls(session):
    a = await FeatureSet().compute(session, "match-up-01", TS)
    b = await FeatureSet().compute(session, "match-up-01", TS)

    assert a == b
    assert a.feature_set_hash == FeatureSet.feature_set_hash()


@pytest.mark.asyncio
async def test_lambdas_respect_clamp_with_outlier_form(session):
    fv = await FeatureSet().compute(session, "match-up-01", TS)
    assert LAMBDA_CLAMP[0] <= fv.lambda_home <= LAMBDA_CLAMP[1]


@pytest.mark.asyncio
async def test_fallbacks_recorded_when_context_missing(session):
    # Un equipo que siempre juega de local no tendrá contexto visitante.
    comp = (await session.execute(select(Competition).where(Competition.external_id == "demo-liga-mx"))).scalar_one()
    season = (await session.execute(select(Season).where(Season.competition_id == comp.id))).scalar_one()
    home_only = Team(external_id="mx-home-only", name="Localista", short_name="LOC")
    other = (await session.execute(select(Team).where(Team.external_id == "mx-ame"))).scalar_one()

    # 8 partidos de local para home_only.
    session.add(home_only)
    await session.flush()
    for i in range(8):
        away = Team(external_id=f"mx-foe-{i}", name=f"Foe{i}", short_name=f"F{i}")
        session.add(away)
        await session.flush()
        session.add(Match(
            external_id=f"hist-loc-{i}",
            season_id=season.id,
            home_team_id=home_only.id,
            away_team_id=away.id,
            kickoff_at=datetime(2026, 7, 5 + i, 20, 0, tzinfo=timezone.utc),
            status="finished",
            home_score=1 + i % 3,
            away_score=i % 2,
        ))
    await session.commit()

    match = Match(
        external_id="match-loc-test",
        season_id=season.id,
        home_team_id=other.id,
        away_team_id=home_only.id,
        kickoff_at=datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc),
        status="scheduled",
    )
    session.add(match)
    await session.commit()

    fv = await FeatureSet().compute(session, "match-loc-test", TS)
    assert fv is not None
    assert any("contexto" in f for f in fv.fallbacks)
