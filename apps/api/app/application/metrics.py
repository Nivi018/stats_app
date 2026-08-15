"""Caso de uso: métricas de evaluación por versión de modelo (US5)."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.evaluation.metrics import (
    MetricsReport,
    ResolvedPrediction,
    compute_metrics,
)
from app.models import ModelVersion, OddsSnapshot, Prediction, PredictionOutcome


class MetricsService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def list_model_versions(self) -> list[ModelVersion]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(ModelVersion).order_by(ModelVersion.created_at)
                )
            ).scalars().all()
            return list(rows)

    async def get_metrics(
        self,
        model_version_id: str | None = None,
        *,
        threshold: int = 30,
        at: datetime | None = None,
    ) -> MetricsReport:
        at = at or datetime.now(UTC)
        async with self._session_factory() as session:
            stmt = (
                select(Prediction, PredictionOutcome)
                .join(PredictionOutcome, PredictionOutcome.prediction_id == Prediction.id)
            )
            if model_version_id is not None:
                stmt = stmt.where(Prediction.model_version_id == model_version_id)
            rows = (await session.execute(stmt)).all()

            records: list[ResolvedPrediction] = []
            for prediction, outcome in rows:
                odds = await self._observed_odds(session, prediction, outcome)
                records.append(
                    ResolvedPrediction(
                        probability=prediction.probability,
                        odds=odds,
                        result=outcome.result,
                    )
                )
        return compute_metrics(
            records,
            model_version_id=model_version_id,
            threshold=threshold,
        )

    async def _observed_odds(self, session, prediction, outcome) -> float | None:
        """Cuota vigente más cercana a la predicción; fallback a cuota justa."""
        snapshot = (
            await session.execute(
                select(OddsSnapshot)
                .where(
                    OddsSnapshot.match_id == prediction.match_id,
                    OddsSnapshot.market == prediction.market,
                    OddsSnapshot.selection == prediction.selection,
                )
                .order_by(OddsSnapshot.observed_at.desc())
            )
        ).scalars().first()
        if snapshot is not None:
            return snapshot.odds
        return prediction.fair_odds
