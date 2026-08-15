"""Demo US4: resolver resultados de predicciones demo de forma asíncrona.

Flujo:
1. Carga el seed demo (idempotente).
2. Encola `compute_prediction` para todos los partidos y procesa la cola.
3. Encola `resolve_prediction` para los partidos finalizados con predicción.
4. Procesa y resume outcomes persistidos por resultado.

Uso:
    python -m app.jobs.run_resolution
"""

import asyncio
import sys
from collections import Counter

from sqlalchemy import select

from app.db.session import async_session
from app.jobs.broker import QueueBroker
from app.jobs.handlers import (
    COMPUTE_PREDICTION_JOB,
    RESOLVE_PREDICTION_JOB,
    build_handlers,
)
from app.jobs.payload import JobEnvelope
from app.jobs.runner import JobRunner
from app.models import Match, Prediction, PredictionOutcome
from app.seeds.loader import load_demo_seed


async def _drain(broker: QueueBroker, runner: JobRunner) -> Counter:
    processed = Counter()
    guard = 0
    while True:
        await broker.move_due()
        if await broker.work_count() == 0:
            break
        outcome = await runner.process_one()
        processed[outcome] += 1
        guard += 1
        if guard > 500:
            raise RuntimeError("Límite de guarda alcanzado procesando la cola")
    return processed


async def _run() -> None:
    async with async_session() as session:
        await load_demo_seed(session)

    async with async_session() as session:
        matches = (
            (await session.execute(select(Match))).scalars().all()
        )

    broker = QueueBroker()
    runner = JobRunner(
        broker=broker,
        session_factory=async_session,
        handlers=build_handlers(async_session),
    )

    print("[demo] Encolando compute_prediction para todos los partidos…")
    for match in matches:
        await broker.enqueue(JobEnvelope(
            job_type=COMPUTE_PREDICTION_JOB,
            idempotency_key=f"demo-compute-{match.external_id}",
            payload={"match_id": match.external_id},
        ))
    stats = await _drain(broker, runner)
    print(f"[demo] Cola de predicción procesada: {dict(stats)}")

    async with async_session() as session:
        resolvable = list(
            (
                await session.execute(
                    select(Match.external_id)
                    .join(Prediction, Prediction.match_id == Match.id)
                    .where(Match.status == "finished")
                    .distinct()
                )
            ).scalars().all()
        )

    print(f"[demo] Partidos finalizados con predicción a resolver: {len(resolvable)}")
    for match_id in resolvable:
        await broker.enqueue(JobEnvelope(
            job_type=RESOLVE_PREDICTION_JOB,
            idempotency_key=f"demo-resolve-{match_id}",
            payload={"match_id": match_id},
        ))
    stats = await _drain(broker, runner)
    print(f"[demo] Cola de resolución procesada: {dict(stats)}")
    await broker.close()

    async with async_session() as session:
        outcomes = (
            (await session.execute(select(PredictionOutcome))).scalars().all()
        )
    by_result = Counter(o.result for o in outcomes)
    print(f"[demo] Outcomes persistidos: {len(outcomes)} -> {dict(by_result)}")


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run())


if __name__ == "__main__":
    main()
