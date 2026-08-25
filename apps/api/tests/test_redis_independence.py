"""Verifica que la historia vive en PostgreSQL y Redis puede vaciarse sin pérdida."""

import pytest
import pytest_asyncio
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Match, OddsSnapshot, Team
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)
REDIS_URL = "redis://127.0.0.1:6380/0"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with session_factory() as s:
        await load_demo_seed(s)
        yield s


@pytest.mark.asyncio
async def test_flush_redis_does_not_lose_history(session):
    matches_before = (await session.execute(select(func.count()).select_from(Match))).scalar()
    teams_before = (await session.execute(select(func.count()).select_from(Team))).scalar()
    odds_before = (await session.execute(select(func.count()).select_from(OddsSnapshot))).scalar()

    r = Redis.from_url(REDIS_URL)
    r.flushdb()
    r.close()

    matches_after = (await session.execute(select(func.count()).select_from(Match))).scalar()
    teams_after = (await session.execute(select(func.count()).select_from(Team))).scalar()
    odds_after = (await session.execute(select(func.count()).select_from(OddsSnapshot))).scalar()

    assert matches_after == matches_before == 42
    assert teams_after == teams_before == 12
    assert odds_after == odds_before == 82  # 60 históricas + 22 próximas


@pytest.mark.asyncio
async def test_redis_remains_reachable_after_flush(session):
    r = Redis.from_url(REDIS_URL)
    r.flushdb()
    r.set("ping-test", "pong", ex=5)
    assert r.get("ping-test") == b"pong"
    r.close()
