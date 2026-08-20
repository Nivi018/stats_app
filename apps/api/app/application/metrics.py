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

            # Cuotas observadas por lote para evitar N+1.
            match_ids = list({p.match_id for p, _ in rows})
            odds_by_key: dict[tuple, float] = {}
            if match_ids:
                snap_rows = (
                    await session.execute(
                        select(OddsSnapshot).where(OddsSnapshot.match_id.in_(match_ids))
                    )
                ).scalars().all()
                best: dict[tuple, tuple[datetime, float]] = {}
                for snapshot in snap_rows:
                    key = (snapshot.match_id, snapshot.market, snapshot.selection)
                    observed = snapshot.observed_at
                    if observed.tzinfo is None:
                        observed = observed.replace(tzinfo=UTC)
                    current = best.get(key)
                    if current is None or observed > current[0]:
                        best[key] = (observed, snapshot.odds)
                odds_by_key = {key: value for key, (_, value) in best.items()}

            records: list[ResolvedPrediction] = []
            for prediction, outcome in rows:
                odds = odds_by_key.get(
                    (prediction.match_id, prediction.market, prediction.selection),
                    prediction.fair_odds,
                )
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
