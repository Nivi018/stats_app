"""Prueba de migraciones desde base vacía y ciclo upgrade/downgrade.

Usa una base dedicada `stats_app_migtest` para no interferir con los demás tests.
Los tests son síncronos porque Alembic gestiona su propio event loop.
"""

import asyncio
import os
import sys

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DIR = os.path.dirname(__file__)
API_DIR = os.path.dirname(TEST_DIR)
ALEMBIC_DIR = os.path.join(API_DIR, "alembic")

ADMIN_DSN = "postgresql://stats:stats@127.0.0.1:5434/postgres"
MIGRATE_DB = "stats_app_migtest"
MIGRATE_URL = f"postgresql+asyncpg://stats:stats@127.0.0.1:5434/{MIGRATE_DB}"
HEAD_REVISION = "06de9ee1fdc3"

_TABLES = {
    "competitions", "seasons", "teams", "matches", "team_match_stats",
    "odds_snapshots", "model_versions", "predictions", "prediction_outcomes",
    "parlays", "job_runs",
}


def _drop_database():
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (MIGRATE_DB,))
            if cur.fetchone():
                cur.execute(f'DROP DATABASE "{MIGRATE_DB}" WITH (FORCE)')


def _create_database():
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{MIGRATE_DB}"')


@pytest.fixture(autouse=True)
def _migrate_db():
    _drop_database()
    _create_database()
    yield
    _drop_database()


def _alembic_config() -> Config:
    cfg = Config(os.path.join(API_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    cfg.set_main_option("sqlalchemy.url", MIGRATE_URL)
    return cfg


def _table_names() -> set[str]:
    async def _query():
        engine = create_async_engine(MIGRATE_URL)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            names = {row[0] for row in result}
        await engine.dispose()
        return names

    return asyncio.run(_query())


def _alembic_version() -> str:
    async def _query():
        engine = create_async_engine(MIGRATE_URL)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
        await engine.dispose()
        return version

    return asyncio.run(_query())


def test_upgrade_head_from_empty():
    command.upgrade(_alembic_config(), "head")

    tables = _table_names()
    assert _TABLES.issubset(tables), f"Missing: {_TABLES - tables}"
    assert _alembic_version() == HEAD_REVISION


def test_downgrade_and_upgrade_cycle():
    command.upgrade(_alembic_config(), "head")
    assert _alembic_version() == HEAD_REVISION

    command.downgrade(_alembic_config(), "base")
    tables = _table_names()
    assert not (_TABLES & tables), f"Tablas residuales tras downgrade: {_TABLES & tables}"

    command.upgrade(_alembic_config(), "head")
    tables = _table_names()
    assert _TABLES.issubset(tables)
    assert _alembic_version() == HEAD_REVISION


def test_migrations_and_seed_idempotent():
    """Aplica migración, siembra dos veces y verifica conteos estables."""
    from sqlalchemy import func, select

    from app.models import Match, Team
    from app.seeds.loader import load_demo_seed

    command.upgrade(_alembic_config(), "head")

    async def _seed_twice():
        engine = create_async_engine(MIGRATE_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await load_demo_seed(session)
            teams_first = (await session.execute(select(func.count()).select_from(Team))).scalar()
            matches_first = (await session.execute(select(func.count()).select_from(Match))).scalar()

            await load_demo_seed(session)
            teams_second = (await session.execute(select(func.count()).select_from(Team))).scalar()
            matches_second = (await session.execute(select(func.count()).select_from(Match))).scalar()
        await engine.dispose()
        return teams_first, matches_first, teams_second, matches_second

    t1, m1, t2, m2 = asyncio.run(_seed_twice())
    assert t1 == t2 == 12
    assert m1 == m2 == 42
