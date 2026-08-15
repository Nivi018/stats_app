import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Competition, Match, OddsSnapshot, Season, Team, TeamMatchStats
from app.seeds.loader import load_demo_seed
from tests.conftest import engine


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s


@pytest.mark.asyncio
async def test_seed_loads_expected_counts(session: AsyncSession):
    await load_demo_seed(session)

    teams = (await session.execute(select(func.count()).select_from(Team))).scalar()
    historical = (await session.execute(
        select(func.count()).select_from(Match).where(Match.status == "finished")
    )).scalar()
    upcoming = (await session.execute(
        select(func.count()).select_from(Match).where(Match.status == "scheduled")
    )).scalar()
    stats = (await session.execute(select(func.count()).select_from(TeamMatchStats))).scalar()
    odds = (await session.execute(select(func.count()).select_from(OddsSnapshot))).scalar()

    assert teams == 12
    assert historical == 30
    assert upcoming == 12
    assert stats == 58
    assert odds == 82  # 60 históricas (prepartido) + 22 próximas


@pytest.mark.asyncio
async def test_seed_is_idempotent(session: AsyncSession):
    await load_demo_seed(session)
    first = (await session.execute(select(func.count()).select_from(Match))).scalar()

    await load_demo_seed(session)
    second = (await session.execute(select(func.count()).select_from(Match))).scalar()
    teams = (await session.execute(select(func.count()).select_from(Team))).scalar()

    assert first == 42
    assert second == 42
    assert teams == 12


@pytest.mark.asyncio
async def test_seed_marks_data_as_demo(session: AsyncSession):
    await load_demo_seed(session)

    matches = (await session.execute(select(Match.is_demo))).scalars().all()
    odds = (await session.execute(select(OddsSnapshot.is_demo))).scalars().all()
    assert all(m is True for m in matches)
    assert all(o is True for o in odds)


@pytest.mark.asyncio
async def test_seed_manifest_is_stable(session: AsyncSession):
    m1 = await load_demo_seed(session)
    m2 = await load_demo_seed(session)

    assert m1.version == "1.0.0"
    assert m1.dataset_hash == m2.dataset_hash
    assert m1.counts["teams"] == 12
    assert "match-hist-30" in m1.intentional_incomplete
    assert "match-up-12" in m1.intentional_incomplete


@pytest.mark.asyncio
async def test_seed_creates_competition_and_season(session: AsyncSession):
    await load_demo_seed(session)

    comp = (await session.execute(
        select(Competition).where(Competition.external_id == "demo-liga-mx")
    )).scalar_one()
    season = (await session.execute(
        select(Season).where(Season.competition_id == comp.id)
    )).scalar_one()

    assert comp.name == "Liga MX"
    assert season.name == "2026 Apertura"
