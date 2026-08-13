"""Handlers de trabajos de ingesta y predicción.

- `ingest_demo` carga el seed de forma idempotente.
- `compute_prediction` calcula el baseline Poisson y persiste la predicción en
  una transacción propia: si falla a mitad, no se publica nada parcial.
"""

from collections.abc import Callable
from datetime import datetime, timezone
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.feature_set import FeatureSet
from app.jobs.runner import DeterministicJobError
from app.model.baseline import MODEL_NAME, PoissonBaseline
from app.models import Match, ModelVersion, Prediction
from app.seeds.loader import load_demo_seed

INGEST_DEMO_JOB = "ingest_demo"
COMPUTE_PREDICTION_JOB = "compute_prediction"


def build_handlers(session_factory=None) -> dict:
    handlers: dict[str, Callable] = {INGEST_DEMO_JOB: ingest_demo}
    if session_factory is not None:
        handlers[COMPUTE_PREDICTION_JOB] = build_compute_prediction_handler(session_factory)
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
                session, match_id, datetime.now(timezone.utc)
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

            now = datetime.now(timezone.utc)
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
            await session.commit()

    return compute_prediction


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
            activated_at=datetime.now(timezone.utc),
        )
        session.add(mv)
        await session.flush()
    return mv
