"""Pruebas del endpoint de backtesting walk-forward (Sprint 9)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client():
    async with session_factory() as session:
        await load_demo_seed(session)
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.session_factory = None


@pytest.mark.asyncio
async def test_backtest_reporte_estructura(client):
    response = await client.get("/api/v1/backtest?folds=4")
    assert response.status_code == 200
    data = response.json()

    assert data["n_folds"] == 4
    assert data["dataset_version"]
    assert len(data["folds"]) == 4
    for section in ("overall", "out_of_sample", "final_holdout"):
        assert section in data
        names = {b["name"] for b in data[section]}
        assert names == {"market", "league", "poisson"}


@pytest.mark.asyncio
async def test_backtest_baselines_metrica_presente(client):
    response = await client.get("/api/v1/backtest")
    data = response.json()

    for baseline in data["out_of_sample"]:
        assert "coverage" in baseline
        assert "candidates_n" in baseline
        assert "brier" in baseline["metrics"] or baseline["metrics"]["sample_size"] == 0


@pytest.mark.asyncio
async def test_backtest_determinista(client):
    a = (await client.get("/api/v1/backtest?folds=4")).json()
    b = (await client.get("/api/v1/backtest?folds=4")).json()
    assert a == b


@pytest.mark.asyncio
async def test_backtest_holdout_final_excluido_de_out_of_sample(client):
    data = (await client.get("/api/v1/backtest?folds=4")).json()
    oos = {b["name"]: b for b in data["out_of_sample"]}
    hold = {b["name"]: b for b in data["final_holdout"]}
    assert oos["poisson"]["coverage_n"] <= hold["poisson"]["coverage_n"] + oos["poisson"]["candidates_n"]