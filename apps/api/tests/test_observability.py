"""Pruebas de observabilidad: logs JSON, correlación, métricas y worker (US7)."""

import io
import json
import logging

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import JsonFormatter, set_correlation_id, set_job_id, setup_logging
from app.jobs.broker import QueueBroker
from app.jobs.handlers import COMPUTE_PREDICTION_JOB, build_handlers
from app.jobs.payload import JobEnvelope
from app.jobs.runner import JobRunner
from app.jobs.worker import process_next
from app.main import app
from app.seeds.loader import load_demo_seed
from tests.conftest import engine

session_factory = async_sessionmaker(engine, expire_on_commit=False)


def _capture_log() -> tuple[io.StringIO, logging.Logger]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(f"test-obsv-{id(stream)}")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return stream, logger


def test_json_log_incluye_contexto():
    stream, logger = _capture_log()
    set_correlation_id("corr-123")
    set_job_id("job-456")
    logger.info("request", extra={"method": "GET", "path": "/api/v1/matchdays/current", "status": 200, "duration_ms": 12.5})

    record = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert record["service"] == "stats-api"
    assert record["release"]  # no vacío
    assert record["correlation_id"] == "corr-123"
    assert record["job_id"] == "job-456"
    assert record["method"] == "GET"
    assert record["status"] == 200
    assert record["duration_ms"] == 12.5
    assert "message" in record


def test_json_log_no_registra_secretos():
    stream, logger = _capture_log()
    set_correlation_id(None)
    set_job_id(None)
    logger.info("auth", extra={"headers": {"authorization": "Bearer secret-token"}})

    payload = stream.getvalue()
    assert "secret-token" not in payload


def test_job_envelope_lleva_correlation_id():
    envelope = JobEnvelope(
        job_type=COMPUTE_PREDICTION_JOB,
        idempotency_key="k-1",
        correlation_id="corr-abc",
    )
    restored = JobEnvelope.from_json(envelope.to_json())
    assert restored.correlation_id == "corr-abc"


@pytest_asyncio.fixture
async def seeded():
    async with session_factory() as session:
        await load_demo_seed(session)


@pytest.mark.asyncio
async def test_correlation_header_echoes_input(seeded):
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/live", headers={"X-Correlation-Id": "corr-from-client"})
    app.state.session_factory = None

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-Id") == "corr-from-client"


@pytest.mark.asyncio
async def test_ops_metrics_expose_estado_de_cola(seeded):
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ops/metrics")
    app.state.session_factory = None

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "stats_queue_backlog" in body
    assert "stats_queue_dlq" in body
    assert "stats_odds_freshness_seconds" in body
    assert "stats_uptime_seconds" in body


@pytest.mark.asyncio
async def test_ops_metrics_refleja_backlog(seeded):
    broker = QueueBroker()
    await broker.flush()
    await broker.enqueue(JobEnvelope(job_type=COMPUTE_PREDICTION_JOB, idempotency_key="m-1", payload={"match_id": "match-up-01"}))
    await broker.enqueue(JobEnvelope(job_type=COMPUTE_PREDICTION_JOB, idempotency_key="m-2", payload={"match_id": "match-up-02"}))
    await broker.close()

    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ops/metrics")
    app.state.session_factory = None

    assert "stats_queue_backlog 2" in response.text


@pytest.mark.asyncio
async def test_worker_process_next_procesa_y_enlaza(seeded):
    broker = QueueBroker()
    await broker.flush()
    runner = JobRunner(
        broker=broker,
        session_factory=session_factory,
        handlers=build_handlers(session_factory),
        backoff_base=0.01,
    )
    await broker.enqueue(JobEnvelope(
        job_type=COMPUTE_PREDICTION_JOB,
        idempotency_key="worker-obs",
        payload={"match_id": "match-up-01"},
        correlation_id="corr-worker",
    ))

    outcome = await process_next(broker, runner, session_factory=session_factory)

    assert outcome == "processed"
    async with session_factory() as session:
        from sqlalchemy import select

        from app.models import JobRun, Prediction

        job_run = (await session.execute(select(JobRun).where(JobRun.idempotency_key == "worker-obs"))).scalar_one()
        assert job_run.status == "completed"
        assert job_run.id  # job_id enlaza la ejecución
        count = len((await session.execute(select(Prediction))).scalars().all())
        assert count == 2
    await broker.close()


def test_setup_logging_configura_handler_json():
    # Verifica que setup_logging instale un formatter JSON en el root logger.
    setup_logging(service="stats-test")
    root = logging.getLogger()
    assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
