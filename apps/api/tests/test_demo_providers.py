import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.providers import (
    InvalidProviderPayload,
    validate_match_status,
    validate_odds,
)
from app.providers.demo import DemoOddsProvider, DemoSportsDataProvider, OddsSnapshotMapper
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s


@pytest_asyncio.fixture
async def seeded(session):
    await load_demo_seed(session)
    return session


@pytest.mark.asyncio
async def test_get_upcoming_matches_normalized(seeded):
    provider = DemoSportsDataProvider(session_factory)
    matches = await provider.get_upcoming_matches()

    assert len(matches) == 12
    for m in matches:
        assert m.competition == "Liga MX"
        assert m.status == "scheduled"
        assert m.home_team.id.startswith("mx-")
        assert m.away_team.id.startswith("mx-")
        assert m.home_team.name
        assert m.away_team.name


@pytest.mark.asyncio
async def test_get_match(seeded):
    provider = DemoSportsDataProvider(session_factory)
    match = await provider.get_match("match-up-01")

    assert match is not None
    assert match.id == "match-up-01"
    assert match.home_team.id == "mx-ame"
    assert match.away_team.id == "mx-caz"


@pytest.mark.asyncio
async def test_get_match_missing_returns_none(seeded):
    provider = DemoSportsDataProvider(session_factory)
    assert await provider.get_match("match-no-existe") is None


@pytest.mark.asyncio
async def test_get_team_match_stats(seeded):
    provider = DemoSportsDataProvider(session_factory)
    stats = await provider.get_team_match_stats("match-hist-01")

    assert len(stats) == 2
    for s in stats:
        assert s.match_id == "match-hist-01"
        assert s.goals >= 0
        assert s.possession is not None


@pytest.mark.asyncio
async def test_get_odds_snapshots(seeded):
    provider = DemoOddsProvider(session_factory)
    odds = await provider.get_odds_snapshots("match-up-01")

    assert len(odds) == 2
    selections = {o.selection for o in odds}
    assert selections == {"over", "under"}
    for o in odds:
        assert o.market == "over_under_2_5"
        assert o.decimal_odds > 1.0
        assert o.provider == "demo-odds"


@pytest.mark.asyncio
async def test_get_odds_incomplete_match_returns_empty(seeded):
    provider = DemoOddsProvider(session_factory)
    assert await provider.get_odds_snapshots("match-up-12") == []


def test_validate_odds_accepts_valid():
    validate_odds("over_under_2_5", "over", 1.85)


def test_validate_odds_rejects_invalid():
    with pytest.raises(InvalidProviderPayload):
        validate_odds("over_under_2_5", "over", 1.0)
    with pytest.raises(InvalidProviderPayload):
        validate_odds("over_under_2_5", "push", 1.85)
    with pytest.raises(InvalidProviderPayload):
        validate_odds("moneyline", "over", 1.85)


def test_validate_match_status_rejects_invalid():
    assert validate_match_status("scheduled") == "scheduled"
    with pytest.raises(InvalidProviderPayload):
        validate_match_status("postponed")


def test_odds_mapper_raises_typed_error_on_bad_payload():
    with pytest.raises(InvalidProviderPayload):
        OddsSnapshotMapper.to_domain(
            match_id="m-1",
            market="over_under_2_5",
            selection="over",
            decimal_odds=0.5,
            captured_at=None,
            provider="demo",
        )
