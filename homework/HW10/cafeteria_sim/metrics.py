from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: Iterable[float], p: float) -> float:
    """Nearest-rank percentile: index = ceil(p / 100 * n) - 1."""

    ordered = sorted(values)
    if not ordered:
        return 0.0
    if not 0 <= p <= 100:
        raise ValueError("p must be between 0 and 100")
    index = max(0, math.ceil(p / 100.0 * len(ordered)) - 1)
    return ordered[index]


def wait_stats(values: Iterable[float]) -> dict[str, float]:
    data = list(values)
    return {
        "count": float(len(data)),
        "mean_s": mean(data),
        "p50_s": percentile(data, 50),
        "p90_s": percentile(data, 90),
        "p95_s": percentile(data, 95),
        "max_s": max(data, default=0.0),
    }


def clamped_interval(start: float, end: float, t0: float, t1: float) -> tuple[float, float]:
    return max(start, t0), min(end, t1)


def interval_total(intervals: Iterable[tuple[float, float]], t0: float, t1: float) -> float:
    total = 0.0
    for start, end in intervals:
        lo, hi = clamped_interval(start, end, t0, t1)
        if hi > lo:
            total += hi - lo
    return total


def max_overlap(intervals: Iterable[tuple[float, float]], t0: float, t1: float) -> int:
    events: list[tuple[float, int]] = []
    for start, end in intervals:
        lo, hi = clamped_interval(start, end, t0, t1)
        if hi > lo:
            events.append((lo, 1))
            events.append((hi, -1))
    events.sort(key=lambda event: (event[0], event[1]))
    current = 0
    peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak
