"""Contrato de trabajos asíncronos.

`JobEnvelope` es el payload versionado que viaja por la cola. La `idempotency_key`
garantiza que una misma entrega no produzca efectos duplicados; `version` permite
evolucionar el contrato sin romper consumidores antiguos.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

JOB_VERSION = "1"


@dataclass
class JobEnvelope:
    job_type: str
    idempotency_key: str
    version: str = JOB_VERSION
    attempt: int = 1
    max_attempts: int = 3
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        import json

        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> "JobEnvelope":
        import json

        data = json.loads(raw)
        return cls(**data)
