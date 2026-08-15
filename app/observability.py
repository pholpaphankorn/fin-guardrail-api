"""Small dependency-free runtime metrics with bounded in-memory latency samples."""

from collections import Counter, deque
from threading import Lock


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


class MetricsRegistry:
    """Track only aggregate operational signals; labels and PII are not accepted."""

    def __init__(self, max_samples: int = 500):
        self._counts: Counter[str] = Counter()
        self._request_latencies: deque[float] = deque(maxlen=max_samples)
        self._model_latencies: deque[float] = deque(maxlen=max_samples)
        self._lock = Lock()

    def increment(self, metric: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[metric] += amount

    def observe_request(self, latency_ms: float) -> None:
        with self._lock:
            self._counts["requests_total"] += 1
            self._request_latencies.append(latency_ms)

    def observe_model(self, latency_ms: float, outcome: str) -> None:
        with self._lock:
            self._counts["model_calls_total"] += 1
            self._counts[f"model_{outcome}_total"] += 1
            self._model_latencies.append(latency_ms)

    def snapshot(self) -> dict:
        with self._lock:
            request_values = list(self._request_latencies)
            model_values = list(self._model_latencies)
            return {
                "counts": dict(sorted(self._counts.items())),
                "request_latency_ms": {
                    "p50": round(_percentile(request_values, 0.50), 3),
                    "p95": round(_percentile(request_values, 0.95), 3),
                    "samples": len(request_values),
                },
                "model_latency_ms": {
                    "p50": round(_percentile(model_values, 0.50), 3),
                    "p95": round(_percentile(model_values, 0.95), 3),
                    "samples": len(model_values),
                },
            }


metrics = MetricsRegistry()
