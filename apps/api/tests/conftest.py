import asyncio
import sys

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models import *  # noqa: F401, F403

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DB_URL = "postgresql+asyncpg://stats:stats@localhost:5433/stats_app"

engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
