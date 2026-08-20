"""Métricas operativas in-process exportables en formato Prometheus (US7).

Cubre latencia y errores HTTP, backlog/retry/DLQ de la cola y frescura de la
última cuota. Es un registro en memoria pensado para el MVP demo.
"""

import time
from collections import Counter, defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self._request_count: Counter = Counter()
        self._error_count: Counter = Counter()
        self._latency_by_path: dict[str, list[float]] = defaultdict(list)
        self._started_at = time.monotonic()

    def record_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        self._request_count[(method, path)] += 1
        if status >= 500:
            self._error_count[(path, status)] += 1
        self._latency_by_path[path].append(duration_ms)

    def latency_p95(self, path: str) -> float:
        values = sorted(self._latency_by_path.get(path, []))
        if not values:
            return 0.0
        index = min(len(values) - 1, int(len(values) * 0.95))
        return values[index]

    def total_requests(self) -> int:
        return sum(self._request_count.values())

    def total_errors(self) -> int:
        return sum(self._error_count.values())

    def render(
        self,
        *,
        queue_backlog: int,
        queue_retry: int,
        queue_dlq: int,
        odds_freshness_seconds: int | None,
    ) -> str:
        lines = [
            f"# TYPE stats_http_requests_total counter",
            f"# TYPE stats_http_errors_total counter",
            f"# TYPE stats_http_latency_p95 gauge",
            f"# TYPE stats_uptime_seconds gauge",
            f"# TYPE stats_queue_backlog gauge",
            f"# TYPE stats_queue_retry gauge",
            f"# TYPE stats_queue_dlq gauge",
            f"# TYPE stats_odds_freshness_seconds gauge",
        ]
        for (method, path), count in sorted(self._request_count.items()):
            lines.append(f'stats_http_requests_total{{method="{method}",path="{path}"}} {count}')
        for (path, status), count in sorted(self._error_count.items()):
            lines.append(
                f'stats_http_errors_total{{path="{path}",status="{status}"}} {count}'
            )
        for path in sorted(self._latency_by_path):
            lines.append(
                f'stats_http_latency_p95{{path="{path}"}} {self.latency_p95(path):.2f}'
            )
        lines.append(f"stats_uptime_seconds {time.monotonic() - self._started_at:.0f}")
        lines.append(f"stats_queue_backlog {queue_backlog}")
        lines.append(f"stats_queue_retry {queue_retry}")
        lines.append(f"stats_queue_dlq {queue_dlq}")
        lines.append(f"stats_odds_freshness_seconds {odds_freshness_seconds if odds_freshness_seconds is not None else 'nan'}")
        return "\n".join(lines) + "\n"


registry = MetricsRegistry()
