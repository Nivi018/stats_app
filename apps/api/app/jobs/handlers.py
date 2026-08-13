"""Handlers de trabajos de ingesta y predicción.

- `ingest_demo` carga el seed de forma idempotente.
- `compute_prediction` calcula el baseline Poisson y persiste la predicción en
  una transacción propia: si falla a mitad, no se publica nada parcial.
"""

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import DeterministicJobError
from app.model.baseline import MODEL_NAME, PoissonBaseline
from app.models import Match, ModelVersion, Prediction, TeamMatchStats
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

            lambda_home, lambda_away = await _baseline_lambdas(session, match.id)

            model_version = await _get_or_create_model_version(session)
            baseline = PoissonBaseline()
            over, under = baseline.predict(lambda_home, lambda_away)

            existing = (
                await session.execute(
                    select(Prediction).where(
                        Prediction.match_id == match.id,
                        Prediction.model_version_id == model_version.id,
                        Prediction.inputs_hash == over.inputs_hash,
                    )
                )
            ).scalar_one_or_none()

            if existing is None:
                now = datetime.now(timezone.utc)
                for selection, prediction in (("over", over), ("under", under)):
                    session.add(
                        Prediction(
                            match_id=match.id,
                            model_version_id=model_version.id,
                            market=baseline.MARKET,
                            selection=selection,
                            probability=prediction.probability,
                            fair_odds=prediction.fair_odds,
                            data_quality="medium",
                            risk_level="medium",
                            inputs_hash=prediction.inputs_hash,
                            prediction_timestamp=now,
                        )
                    )
            await session.commit()

    return compute_prediction


async def _baseline_lambdas(session: AsyncSession, match_id) -> tuple[float, float]:
    """Lambdas placeholder desde goles promedios del dataset demo.

    El FeatureSet v1 (historia posterior) refinará este cálculo con ventanas,
    localía y ponderación temporal.
    """
    rows = (
        await session.execute(
            select(TeamMatchStats.team_id, func.avg(TeamMatchStats.goals))
            .where(TeamMatchStats.match_id == match_id)
            .group_by(TeamMatchStats.team_id)
        )
    ).all()
    averages = {str(team_id): float(avg) for team_id, avg in rows}

    result = await session.execute(
        select(Match).where(Match.id == match_id)
    )
    match = result.scalar_one()
    lambda_home = averages.get(str(match.home_team_id), 1.3)
    lambda_away = averages.get(str(match.away_team_id), 1.1)
    return lambda_home, lambda_away


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
