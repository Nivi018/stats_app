"""Handlers de trabajos de ingesta.

`ingest_demo` carga el seed de forma idempotente; la idempotencia se refuerza
tanto por el propio loader (claves naturales) como por el JobRun completado.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import DeterministicJobError
from app.seeds.loader import load_demo_seed

INGEST_DEMO_JOB = "ingest_demo"


def build_handlers() -> dict:
    return {INGEST_DEMO_JOB: ingest_demo}


async def ingest_demo(payload: dict, session: AsyncSession) -> None:
    version = payload.get("version")
    if version is None:
        raise DeterministicJobError("Payload de ingesta inválido: falta 'version'")
    await load_demo_seed(session)
