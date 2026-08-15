"""Caso de uso: historial paginado de resultados resueltos (US6)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.models import Match, ModelVersion, Prediction, PredictionOutcome, Team


@dataclass(frozen=True)
class HistoryItem:
    prediction_id: UUID
    match_id: str
    home_team_short: str
    away_team_short: str
    kickoff_at: datetime
    market: str
    selection: str
    probability: float
    odds: float | None
    model_version: str
    prediction_timestamp: datetime
    result: str
    resolved_at: datetime


@dataclass(frozen=True)
class HistoryPage:
    items: list[HistoryItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class HistoryService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def get_history(
        self,
        *,
        model_version: str | None = None,
        result: str | None = None,
        matchday: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> HistoryPage:
        home = aliased(Team)
        away = aliased(Team)

        joins = (
            select(PredictionOutcome, Prediction, Match, ModelVersion, home, away)
            .join(Prediction, Prediction.id == PredictionOutcome.prediction_id)
            .join(ModelVersion, ModelVersion.id == Prediction.model_version_id)
            .join(Match, Match.id == Prediction.match_id)
            .join(home, home.id == Match.home_team_id)
            .join(away, away.id == Match.away_team_id)
        )
        filters = self._filters(model_version=model_version, result=result, matchday=matchday)

        async with self._session_factory() as session:
            filtered = joins.where(*filters)
            total = (
                await session.execute(select(func.count()).select_from(filtered.subquery()))
            ).scalar() or 0

            rows = (
                await session.execute(
                    filtered.order_by(PredictionOutcome.resolved_at.desc(), PredictionOutcome.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()

        total_pages = (total + page_size - 1) // page_size if total else 0
        items = [
            HistoryItem(
                prediction_id=outcome.prediction_id,
                match_id=match.external_id,
                home_team_short=home.short_name or home.name,
                away_team_short=away.short_name or away.name,
                kickoff_at=match.kickoff_at,
                market=prediction.market,
                selection=prediction.selection,
                probability=prediction.probability,
                odds=prediction.fair_odds,
                model_version=model.version,
                prediction_timestamp=prediction.prediction_timestamp,
                result=outcome.result,
                resolved_at=outcome.resolved_at,
            )
            for outcome, prediction, match, model, home, away in rows
        ]
        return HistoryPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    @staticmethod
    def _filters(*, model_version: str | None, result: str | None, matchday: int | None):
        conditions = []
        if model_version is not None:
            conditions.append(ModelVersion.version == model_version)
        if result is not None:
            conditions.append(PredictionOutcome.result == result)
        if matchday is not None:
            conditions.append(Match.matchday == matchday)
        return conditions
