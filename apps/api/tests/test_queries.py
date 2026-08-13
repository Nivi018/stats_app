"""Auditoría de consultas críticas (sin N+1) y de relaciones/constraints."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Match, Team, TeamMatchStats
from app.providers.demo import DemoSportsDataProvider
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


class QueryCounter:
    def __init__(self) -> None:
        self.count = 0
        self._handle = event.listen(engine.sync_engine, "before_cursor_execute", self._count)

    def _count(self, *args, **kwargs):
        self.count += 1

    def reset(self) -> None:
        self.count = 0

    def detach(self) -> None:
        event.remove(engine.sync_engine, "before_cursor_execute", self._count)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with session_factory() as s:
        await load_demo_seed(s)
        yield s


@pytest.mark.asyncio
async def test_upcoming_matches_no_n_plus_1(session):
    """get_upcoming_matches usa joins: debe ejecutar 1 consulta, no 1+12."""
    counter = QueryCounter()
    try:
        provider = DemoSportsDataProvider(session_factory)
        matches = await provider.get_upcoming_matches()
        assert len(matches) == 12
        assert counter.count <= 2, f"Demasiadas consultas: {counter.count}"
    finally:
        counter.detach()


@pytest.mark.asyncio
async def test_get_match_single_query(session):
    counter = QueryCounter()
    try:
        provider = DemoSportsDataProvider(session_factory)
        match = await provider.get_match("match-up-01")
        assert match is not None
        assert counter.count <= 2, f"Demasiadas consultas: {counter.count}"
    finally:
        counter.detach()


@pytest.mark.asyncio
async def test_stats_and_odds_per_match_are_bounded(session):
    """Por partido, stats y odds usan consultas indexadas (por match), no scans."""
    counter = QueryCounter()
    try:
        provider = DemoSportsDataProvider(session_factory)
        stats = await provider.get_team_match_stats("match-hist-01")
        assert len(stats) == 2
        assert counter.count == 1
    finally:
        counter.detach()


@pytest.mark.asyncio
async def test_foreign_key_blocks_invalid_match(session):
    """Un partido con equipo inexistente debe ser rechazado por la BD."""
    stmt = select(Match).limit(1)
    existing = (await session.execute(stmt)).scalar_one()
    bogus = Match(
        external_id="fk-invalid",
        season_id=existing.season_id,
        home_team_id=uuid.uuid4(),
        away_team_id=existing.away_team_id,
        kickoff_at=existing.kickoff_at,
        status="scheduled",
    )
    session.add(bogus)
    with pytest.raises(Exception):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_unique_team_in_match_stats(session):
    """Dos filas de stats para el mismo match+team deben ser rechazadas."""
    stats = (await session.execute(select(TeamMatchStats).limit(1))).scalar_one()
    dup = TeamMatchStats(
        match_id=stats.match_id,
        team_id=stats.team_id,
        goals=stats.goals,
    )
    session.add(dup)
    with pytest.raises(Exception):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_team_relation_integrity(session):
    """Equipos referenciados por partidos existen (integridad referencial)."""
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM matches m "
            "LEFT JOIN teams h ON m.home_team_id = h.id "
            "LEFT JOIN teams a ON m.away_team_id = a.id "
            "WHERE h.id IS NULL OR a.id IS NULL"
        )
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_seed_does_not_duplicate_teams(session):
    """La carga doble no crea equipos duplicados (idempotencia)."""
    await load_demo_seed(session)
    count = (await session.execute(select(func.count()).select_from(Team))).scalar()
    assert count == 12
