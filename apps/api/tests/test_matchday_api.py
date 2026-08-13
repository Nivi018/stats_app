import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded_session() -> AsyncSession:
    async with session_factory() as session:
        await load_demo_seed(session)
        yield session


@pytest_asyncio.fixture
async def client(seeded_session):
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.session_factory = None


@pytest.mark.asyncio
async def test_matchdays_current(client):
    response = await client.get("/api/v1/matchdays/current")
    assert response.status_code == 200
    data = response.json()
    assert data["matchday"] == 1
    assert data["total_matches"] == 12
    assert len(data["matches"]) == 12

    match = data["matches"][0]
    assert match["competition"] == "Liga MX"
    assert match["status"] == "scheduled"
    assert match["home_team"]["id"].startswith("mx-")
    assert match["over_odds"] is not None
    assert match["under_odds"] is not None


@pytest.mark.asyncio
async def test_matchday_with_incomplete_odds(client):
    response = await client.get("/api/v1/matchdays/current")
    matches = response.json()["matches"]
    match_up_12 = next(m for m in matches if m["id"] == "match-up-12")
    assert match_up_12["over_odds"] is None
    assert match_up_12["under_odds"] is None


@pytest.mark.asyncio
async def test_match_detail(client):
    response = await client.get("/api/v1/matches/match-hist-01")
    assert response.status_code == 200
    data = response.json()
    assert data["match"]["id"] == "match-hist-01"
    assert data["match"]["status"] == "finished"
    assert len(data["stats"]) == 2
    assert all(s["goals"] >= 0 for s in data["stats"])


@pytest.mark.asyncio
async def test_match_detail_404_has_correlation_id(client):
    response = await client.get("/api/v1/matches/no-existe")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "not_found"
    assert "correlation_id" in data
    assert data["correlation_id"]
    assert response.headers.get("X-Correlation-Id") == data["correlation_id"]


@pytest.mark.asyncio
async def test_match_odds(client):
    response = await client.get("/api/v1/matches/match-up-01/odds")
    assert response.status_code == 200
    odds = response.json()
    assert len(odds) == 2
    assert {o["selection"] for o in odds} == {"over", "under"}
    assert all(o["decimal_odds"] > 1.0 for o in odds)


@pytest.mark.asyncio
async def test_match_odds_empty_for_incomplete(client):
    response = await client.get("/api/v1/matches/match-up-12/odds")
    assert response.status_code == 200
    assert response.json() == []
