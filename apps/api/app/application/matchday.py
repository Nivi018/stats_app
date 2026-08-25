"""Capa de aplicación: casos de uso que componen los adaptadores demo.

La API depende de estos servicios; nunca accede a PostgreSQL directamente.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import DomainMatch, DomainOddsSnapshot, DomainTeamMatchStats
from app.models import Match, OddsSnapshot, Prediction
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

    async def get_current_matchday_with_odds(
        self,
    ) -> list[tuple[DomainMatch, DomainOddsSnapshot | None, DomainOddsSnapshot | None]]:
        """Jornada con cuotas Over/Under en 2 consultas (sin N+1)."""
        matches = await self._sports.get_upcoming_matches()
        grouped = await self._odds.get_odds_snapshots_for_matches([m.id for m in matches])
        result: list[tuple[DomainMatch, DomainOddsSnapshot | None, DomainOddsSnapshot | None]] = []
        for match in matches:
            odds = grouped.get(match.id, [])
            over = next((o for o in odds if o.selection == "over"), None)
            under = next((o for o in odds if o.selection == "under"), None)
            result.append((match, over, under))
        return result

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
            result = await session.execute(
                select(Prediction).where(Prediction.id == prediction_uuid)
            )
            return result.scalar_one_or_none()

    async def get_prediction_freshness(self, prediction: Prediction, at=None) -> float:
        """Antigüedad de la cuota vigente más cercana a la predicción (segundos)."""
        at = at or datetime.now(UTC)
        async with self._session_factory() as session:
            observed = (
                await session.execute(
                    select(OddsSnapshot.observed_at)
                    .where(
                        OddsSnapshot.match_id == prediction.match_id,
                        OddsSnapshot.market == prediction.market,
                        OddsSnapshot.selection == prediction.selection,
                    )
                    .order_by(OddsSnapshot.observed_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if observed is None:
            return float("inf")
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        return max(0, (at - observed).total_seconds())
