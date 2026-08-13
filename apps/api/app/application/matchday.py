"""Capa de aplicación: casos de uso que componen los adaptadores demo.

La API depende de estos servicios; nunca accede a PostgreSQL directamente.
"""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import DomainMatch, DomainOddsSnapshot, DomainTeamMatchStats
from app.providers.demo import DemoOddsProvider, DemoSportsDataProvider


class MatchdayService:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | None = None,
        sports: DemoSportsDataProvider | None = None,
        odds: DemoOddsProvider | None = None,
    ) -> None:
        self._sports = sports or DemoSportsDataProvider(session_factory)
        self._odds = odds or DemoOddsProvider(session_factory)

    async def get_current_matchday(self) -> list[DomainMatch]:
        return await self._sports.get_upcoming_matches()

    async def get_match(self, match_id: str) -> DomainMatch | None:
        return await self._sports.get_match(match_id)

    async def get_match_stats(self, match_id: str) -> list[DomainTeamMatchStats]:
        return await self._sports.get_team_match_stats(match_id)

    async def get_match_odds(self, match_id: str) -> list[DomainOddsSnapshot]:
        return await self._odds.get_odds_snapshots(match_id)
