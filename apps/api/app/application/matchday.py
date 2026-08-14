"""Capa de aplicación: casos de uso que componen los adaptadores demo.

La API depende de estos servicios; nunca accede a PostgreSQL directamente.
"""

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import DomainMatch, DomainOddsSnapshot, DomainTeamMatchStats
from app.models import Match, Prediction
from app.providers.demo import DemoOddsProvider, DemoSportsDataProvider


class MatchdayService:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | None = None,
        sports: DemoSportsDataProvider | None = None,
        odds: DemoOddsProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
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

    async def get_match_predictions(self, match_id: str) -> list[Prediction]:
        """Última predicción por selección para un partido."""
        if self._session_factory is None:
            return []
        async with self._session_factory() as session:
            match = (
                await session.execute(select(Match).where(Match.external_id == match_id))
            ).scalar_one_or_none()
            if match is None:
                return []
            preds = (
                await session.execute(
                    select(Prediction)
                    .where(Prediction.match_id == match.id)
                    .order_by(Prediction.prediction_timestamp.desc())
                )
            ).scalars().all()
            latest: dict[str, Prediction] = {}
            for pred in preds:
                latest.setdefault(pred.selection, pred)
            return list(latest.values())

    async def get_prediction(self, prediction_id: str) -> Prediction | None:
        if self._session_factory is None:
            return None
        try:
            prediction_uuid = uuid.UUID(prediction_id)
        except ValueError:
            return None
        async with self._session_factory() as session:
            result = await session.execute(select(Prediction).where(Prediction.id == prediction_uuid))
            return result.scalar_one_or_none()
