from __future__ import annotations

import random
from collections.abc import Callable

Sampler = Callable[[], float]


def make_sampler(name: str, mean: float, rng: random.Random) -> Sampler:
    """Return a positive service-time sampler with the requested mean."""

    if mean <= 0:
        raise ValueError("mean must be positive")

    if name == "exponential":
        rate = 1.0 / mean
        return lambda: rng.expovariate(rate)

    if name == "deterministic":
        return lambda: mean

    if name == "uniform":
        return lambda: rng.uniform(0.5 * mean, 1.5 * mean)

    if name == "triangular":
        return lambda: rng.triangular(0.5 * mean, mean, 1.5 * mean)

    raise ValueError(f"unknown distribution: {name}")
