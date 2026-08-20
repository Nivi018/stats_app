"""Broker de cola sobre Redis.

Redis solo coordina: enqueue/dequeue, reintentos con backoff (zset por
timestamp) y dead-letter queue. El estado durable vive en PostgreSQL (JobRun),
de modo que perder Redis no borra historia.
"""

import json
import time

import redis.asyncio as redis

from app.jobs.payload import JobEnvelope

DEFAULT_REDIS_URL = "redis://localhost:6379/0"


class QueueBroker:
    def __init__(self, url: str = DEFAULT_REDIS_URL) -> None:
        self._r = redis.Redis.from_url(url, decode_responses=True)

    @property
    def work_key(self) -> str:
        return "stats:queue:ingest"

    @property
    def retry_key(self) -> str:
        return "stats:queue:ingest:retry"

    @property
    def dlq_key(self) -> str:
        return "stats:queue:ingest:dlq"

    async def enqueue(self, envelope: JobEnvelope) -> None:
        await self._r.rpush(self.work_key, envelope.to_json())

    async def dequeue(self) -> JobEnvelope | None:
        raw = await self._r.lpop(self.work_key)
        if raw is None:
            return None
        return JobEnvelope.from_json(raw)

    async def peek(self) -> JobEnvelope | None:
        """Devuelve el trabajo al frente sin retirarlo (para logging/contexto)."""
        raw = await self._r.lindex(self.work_key, 0)
        if raw is None:
            return None
        return JobEnvelope.from_json(raw)

    async def retry_count(self) -> int:
        return int(await self._r.zcard(self.retry_key))

    async def move_due(self, now: float | None = None) -> int:
        """Mueve trabajos reintentables vencidos desde el zset a la cola de trabajo."""
        now = now or time.time()
        due = await self._r.zrangebyscore(self.retry_key, 0, now)
        if not due:
            return 0
        await self._r.zrem(self.retry_key, *due)
        for raw in due:
            await self._r.rpush(self.work_key, raw)
        return len(due)

    async def requeue_with_backoff(self, envelope: JobEnvelope, delay_seconds: float) -> None:
        score = time.time() + delay_seconds
        await self._r.zadd(self.retry_key, {envelope.to_json(): score})

    async def send_dlq(self, envelope: JobEnvelope) -> None:
        await self._r.rpush(self.dlq_key, envelope.to_json())

    async def dlq_count(self) -> int:
        return int(await self._r.llen(self.dlq_key))

    async def work_count(self) -> int:
        return int(await self._r.llen(self.work_key))

    async def drain_dlq(self) -> list[JobEnvelope]:
        raws = await self._r.lrange(self.dlq_key, 0, -1)
        await self._r.delete(self.dlq_key)
        return [JobEnvelope.from_json(raw) for raw in raws]

    async def flush(self) -> None:
        await self._r.flushdb()

    async def close(self) -> None:
        await self._r.aclose()
