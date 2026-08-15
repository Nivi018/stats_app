"""Pruebas del endpoint de estimación del parlay (US2/US3)."""

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
    from app.jobs.broker import QueueBroker
    from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
    from app.jobs.payload import JobEnvelope
    from app.jobs.runner import JobRunner

    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(broker=broker, session_factory=session_factory, handlers=build_handlers(session_factory))
    for match_id in ("match-up-01", "match-up-02", "match-up-05", "match-up-12"):
        await broker.enqueue(JobEnvelope(
            job_type=COMPUTE_PREDICTION_JOB,
            idempotency_key=f"parlay-pred-{match_id}",
            payload={"match_id": match_id},
        ))
        await runner.process_one()
    await broker.close()

    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.session_factory = None


def _payload(*refs):
    return {"selections": [dict(r) for r in refs]}


def _ref(match_id: str, selection: str, market: str = "over_under_2_5") -> dict:
    return {"match_id": match_id, "market": market, "selection": selection}


@pytest.mark.asyncio
async def test_estimate_independent_selections(client):
    response = await client.post(
        "/api/v1/parlays/estimate",
        json=_payload(_ref("match-up-01", "over"), _ref("match-up-02", "under")),
    )
    assert response.status_code == 200
    data = response.json()

    assert data["selection_count"] == 2
    assert len(data["selections"]) == 2
    assert data["combined_odds"] > 1.0
    assert data["estimated_probability"] == pytest.approx(data["naive_probability"])
    assert data["correlation_warnings"] == []
    assert data["risk_level"] in {"low", "medium", "high"}
    assert data["risk_factors"]
    assert data["selections"][0]["home_team_short"]
    assert data["selections"][0]["odds"] > 1.0


@pytest.mark.asyncio
async def test_estimate_same_match_exclusive(client):
    response = await client.post(
        "/api/v1/parlays/estimate",
        json=_payload(_ref("match-up-01", "over"), _ref("match-up-01", "under")),
    )
    assert response.status_code == 200
    data = response.json()

    assert data["estimated_probability"] == 0.0
    assert data["fair_combined_odds"] is None
    assert data["risk_level"] == "high"
    assert any("excluyentes" in w for w in data["correlation_warnings"])


@pytest.mark.asyncio
async def test_estimate_same_team_warns_and_marks_independence(client):
    # AME juega en match-up-01 y match-up-05 (mx-leo vs mx-ame).
    response = await client.post(
        "/api/v1/parlays/estimate",
        json=_payload(_ref("match-up-01", "over"), _ref("match-up-05", "over")),
    )
    assert response.status_code == 200
    data = response.json()

    assert data["assumes_independence"] is True
    assert any("correlacionados" in w for w in data["correlation_warnings"])


@pytest.mark.asyncio
async def test_estimate_rejects_more_than_three(client):
    response = await client.post(
        "/api/v1/parlays/estimate",
        json=_payload(
            _ref("match-up-01", "over"),
            _ref("match-up-02", "over"),
            _ref("match-up-03", "over"),
            _ref("match-up-04", "over"),
        ),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unresolvable_selection"


@pytest.mark.asyncio
async def test_estimate_unresolvable_selection_returns_422(client):
    response = await client.post(
        "/api/v1/parlays/estimate",
        json=_payload(_ref("match-up-12", "over")),  # sin cuotas en el seed
    )
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "unresolvable_selection"
    assert "Sin cuota" in data["message"]
    assert "correlation_id" in data
