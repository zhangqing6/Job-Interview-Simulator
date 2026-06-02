"""In-process metrics for latency, concurrency, rounds, and scoring (JSON / logs)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _LatencyBucket:
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0

    def record(self, ms: float) -> None:
        self.count += 1
        self.total_ms += ms
        self.max_ms = max(self.max_ms, ms)

    def to_dict(self) -> dict[str, Any]:
        if self.count == 0:
            return {"count": 0, "avg_ms": 0.0, "max_ms": 0.0}
        return {
            "count": self.count,
            "avg_ms": round(self.total_ms / self.count, 2),
            "max_ms": round(self.max_ms, 2),
        }


class MetricsRegistry:
    """Thread-safe counters/histograms (single process; aggregate via log shipping)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latencies: dict[str, _LatencyBucket] = defaultdict(_LatencyBucket)
        self._counters: dict[str, int] = defaultdict(int)
        self._weighted_scores: list[float] = []
        self._active_sessions = 0

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def session_started(self) -> None:
        with self._lock:
            self._active_sessions += 1
            self._counters["sessions_started"] += 1

    def session_ended(self) -> None:
        with self._lock:
            self._active_sessions = max(0, self._active_sessions - 1)
            self._counters["sessions_ended"] += 1

    def record_latency(self, operation: str, duration_ms: float) -> None:
        with self._lock:
            self._latencies[operation].record(duration_ms)

    def record_weighted_score(self, value: float) -> None:
        with self._lock:
            self._weighted_scores.append(value)
            if len(self._weighted_scores) > 10_000:
                self._weighted_scores = self._weighted_scores[-5_000:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            scores = list(self._weighted_scores)
            latencies = {k: v.to_dict() for k, v in self._latencies.items()}
            counters = dict(self._counters)
            active = self._active_sessions

        score_stats: dict[str, Any] = {"samples": len(scores)}
        if scores:
            scores_sorted = sorted(scores)
            n = len(scores_sorted)
            score_stats.update(
                {
                    "min": round(scores_sorted[0], 3),
                    "max": round(scores_sorted[-1], 3),
                    "mean": round(sum(scores_sorted) / n, 3),
                    "p50": round(scores_sorted[n // 2], 3),
                    "p90": round(scores_sorted[int(n * 0.9)], 3) if n > 1 else score_stats["mean"],
                }
            )

        return {
            "active_sessions": active,
            "counters": counters,
            "latencies_ms": latencies,
            "weighted_score_distribution": score_stats,
        }


_registry = MetricsRegistry()


def get_metrics() -> MetricsRegistry:
    return _registry


class observe_ms:
    """Context manager: ``with observe_ms('ask_total'): ...``"""

    def __init__(self, operation: str) -> None:
        self._operation = operation
        self._start = 0.0

    def __enter__(self) -> observe_ms:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        ms = (time.perf_counter() - self._start) * 1000
        get_metrics().record_latency(self._operation, ms)


__all__ = ["MetricsRegistry", "get_metrics", "observe_ms"]
