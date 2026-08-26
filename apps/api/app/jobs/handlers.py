"""Handlers de trabajos de ingesta y predicción.

- `ingest_demo` carga el seed de forma idempotente.
- `compute_prediction` calcula el baseline Poisson y persiste la predicción en
  una transacción propia: si falla a mitad, no se publica nada parcial.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.resolve import resolve_outcome
from app.features.feature_set import FeatureSet
from app.jobs.runner import DeterministicJobError, TransientJobError
from app.model.baseline import MODEL_NAME, PoissonBaseline
from app.models import Match, ModelVersion, Prediction, PredictionOutcome
from app.seeds.loader import load_demo_seed

INGEST_DEMO_JOB = "ingest_demo"
COMPUTE_PREDICTION_JOB = "compute_prediction"
RESOLVE_PREDICTION_JOB = "resolve_prediction"


def build_handlers(session_factory=None) -> dict:
    handlers: dict[str, Callable] = {INGEST_DEMO_JOB: ingest_demo}
    if session_factory is not None:
        handlers[COMPUTE_PREDICTION_JOB] = build_compute_prediction_handler(session_factory)
        handlers[RESOLVE_PREDICTION_JOB] = build_resolve_prediction_handler(session_factory)
    return handlers


async def ingest_demo(payload: dict, session: AsyncSession) -> None:
    version = payload.get("version")
    if version is None:
        raise DeterministicJobError("Payload de ingesta inválido: falta 'version'")
    await load_demo_seed(session)


def build_compute_prediction_handler(session_factory):
    """Crea el handler de predicción con su propia fábrica de sesiones.

    Usa una sesión independiente para que la persistencia de la predicción sea
    atómica y no se mezcle con la actualización del JobRun.
    """

    async def compute_prediction(payload: dict, _session: AsyncSession) -> None:
        match_id = payload.get("match_id")
        if match_id is None:
            raise DeterministicJobError("Payload inválido: falta 'match_id'")

        async with session_factory() as session:
            match = (
                await session.execute(select(Match).where(Match.external_id == match_id))
            ).scalar_one_or_none()
            if match is None:
                raise DeterministicJobError(f"Partido no encontrado: {match_id}")

            feature_vector = await FeatureSet().compute(
                session, match_id, datetime.now(UTC)
            )
            if feature_vector is None:
                raise DeterministicJobError(
                    f"Sin muestra suficiente para predecir: {match_id}"
                )
            lambda_home = feature_vector.lambda_home
            lambda_away = feature_vector.lambda_away

            model_version = await _get_or_create_model_version(session)
            baseline = PoissonBaseline()
            over, under = baseline.predict(lambda_home, lambda_away)

            now = datetime.now(UTC)
            inputs_json = json.dumps(
                {
                    "lambda_home": lambda_home,
                    "lambda_away": lambda_away,
                    "model_version": baseline.MODEL_VERSION,
                    "feature_set_version": model_version.feature_set_version,
                    "dataset": "demo-2026-apertura",
                },
                sort_keys=True,
            )
            for selection, prediction in (("over", over), ("under", under)):
                session.add(
                    Prediction(
                        match_id=match.id,
                        model_version_id=model_version.id,
                        market=baseline.MARKET,
                        selection=selection,
                        probability=prediction.probability,
                        fair_odds=prediction.fair_odds,
                        data_quality=feature_vector.data_quality,
                        risk_level=feature_vector.risk_level,
                        inputs=inputs_json,
                        inputs_hash=prediction.inputs_hash,
                        prediction_timestamp=now,
                    )
                )

            for market, selection, line, probability, fair in _derived_markets(
                lambda_home, lambda_away
            ):
                session.add(
                    Prediction(
                        match_id=match.id,
                        model_version_id=model_version.id,
                        market=market,
                        selection=selection,
                        line=line,
                        probability=probability,
                        fair_odds=fair,
                        data_quality=feature_vector.data_quality,
                        risk_level=feature_vector.risk_level,
                        inputs=inputs_json,
                        inputs_hash=_hash_of(inputs_json),
                        prediction_timestamp=now,
                    )
                )
            await session.commit()

    return compute_prediction


def _derived_markets(lambda_home: float, lambda_away: float):
    """Predicciones extra de 1X2, totales por equipo y hándicap."""
    from app.domain.odds import fair_odds, round_to
    from app.model.markets import (
        probability_1x2,
        probability_handicap,
        probability_team_total,
        score_matrix,
    )

    matrix = score_matrix(lambda_home, lambda_away)
    rows: list[tuple[str, str, float | None, float, float]] = []

    def add(market: str, selection: str, p: float, line: float | None = None):
        if p <= 0:
            return
        rows.append((market, selection, line, round(p, 6), round_to(fair_odds(p), 4)))

    p_home, p_draw, p_away = probability_1x2(matrix)
    add("1x2", "home", p_home)
    add("1x2", "draw", p_draw)
    add("1x2", "away", p_away)

    for team, market in (("home", "home_total"), ("away", "away_total")):
        for outcome in ("over", "under"):
            p = probability_team_total(
                matrix, team=team, outcome=outcome, line=1.5
            )
            add(market, outcome, p, 1.5)

    for key, selection in (
        ("home", "cover"),
        ("home", "not_cover"),
        ("away", "cover"),
        ("away", "not_cover"),
    ):
        p = probability_handicap(
            matrix, team=key, line=-1, covers=selection == "cover"
        )
        add(f"handicap_{key}", selection, p, -1)

    return rows


def _hash_of(inputs_json: str) -> str:
    import hashlib

    return hashlib.sha256(inputs_json.encode("utf-8")).hexdigest()


def build_resolve_prediction_handler(session_factory):
    """Resuelve las predicciones de un partido finalizado (US4).

    No muta `Prediction`: crea `PredictionOutcome` por predicción, idempotente
    por la unicidad de `prediction_id`. Si el partido no está finalizado, es
    un error transitorio y se reintenta.
    """

    async def resolve_prediction(payload: dict, _session: AsyncSession) -> None:
        match_id = payload.get("match_id")
        if match_id is None:
            raise DeterministicJobError("Payload inválido: falta 'match_id'")

        async with session_factory() as session:
            match = (
                await session.execute(select(Match).where(Match.external_id == match_id))
            ).scalar_one_or_none()
            if match is None:
                raise DeterministicJobError(f"Partido no encontrado: {match_id}")

            if match.status != "finished":
                raise TransientJobError(
                    f"Partido sin resultado final aún ({match.status}); reintentar más tarde"
                )

            predictions = (
                await session.execute(
                    select(Prediction).where(Prediction.match_id == match.id)
                )
            ).scalars().all()
            if not predictions:
                raise DeterministicJobError(f"Sin predicciones para resolver: {match_id}")

            now = datetime.now(UTC)
            total_goals = (match.home_score or 0) + (match.away_score or 0)
            persisted = 0
            for prediction in predictions:
                existing = (
                    await session.execute(
                        select(PredictionOutcome).where(
                            PredictionOutcome.prediction_id == prediction.id
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    continue  # idempotencia: no duplicar
                result = resolve_outcome(
                    prediction.market,
                    prediction.selection,
                    match.home_score,
                    match.away_score,
                )
                session.add(
                    PredictionOutcome(
                        prediction_id=prediction.id,
                        result=result,
                        resolved_at=now,
                        home_score=match.home_score,
                        away_score=match.away_score,
                        total_goals=total_goals,
                    )
                )
                persisted += 1
            await session.commit()

    return resolve_prediction


async def _get_or_create_model_version(session: AsyncSession) -> ModelVersion:
    stmt = select(ModelVersion).where(
        ModelVersion.name == MODEL_NAME,
        ModelVersion.version == PoissonBaseline.MODEL_VERSION,
    )
    mv = (await session.execute(stmt)).scalar_one_or_none()
    if mv is None:
        mv = ModelVersion(
            name=MODEL_NAME,
            version=PoissonBaseline.MODEL_VERSION,
            status="candidate",
            feature_set_version="1.0.0",
            activated_at=datetime.now(UTC),
        )
        session.add(mv)
        await session.flush()
    return mv
