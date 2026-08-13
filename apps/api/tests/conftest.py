import asyncio
import os
import sys

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models import *  # noqa: F401, F403

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://stats:stats@localhost:5433/stats_app",
)

engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest_asyncio.fixture(autouse=True)
async def _clean_between_tests():
    """Limpia todas las tablas antes de cada test para aislarlos."""
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield
