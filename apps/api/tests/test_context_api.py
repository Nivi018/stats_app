"""Pruebas del endpoint de contexto de partido (Sprint 8)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded():
    async with session_factory() as session:
        await load_demo_seed(session)


@pytest_asyncio.fixture
async def client(seeded):
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.session_factory = None


@pytest.mark.asyncio
async def test_context_partido_proximo_con_forma_y_h2h(client):
    response = await client.get("/api/v1/matches/match-up-01/context")
    assert response.status_code == 200
    data = response.json()

    assert data["home_form"] or data["away_form"] or data["h2h"]
    for entry in data["home_form"] + data["away_form"] + data["h2h"]:
        assert entry["result"] in {"W", "D", "L"}
        assert entry["home_goals"] >= 0
        assert entry["away_goals"] >= 0
        assert entry["kickoff_at"]


@pytest.mark.asyncio
async def test_context_forma_limitada_a_cinco(client):
    response = await client.get("/api/v1/matches/match-up-01/context")
    data = response.json()
    assert len(data["home_form"]) <= 5
    assert len(data["away_form"]) <= 5
    assert len(data["h2h"]) <= 5


@pytest.mark.asyncio
async def test_context_404_partido_inexistente(client):
    response = await client.get("/api/v1/matches/no-existe/context")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.asyncio
async def test_context_opponentes_tienen_nombre_corto(client):
    response = await client.get("/api/v1/matches/match-up-01/context")
    data = response.json()
    for entry in data["home_form"] + data["h2h"]:
        assert entry["opponent_short"]  # nombre corto del rival