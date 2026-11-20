from __future__ import annotations

from dataclasses import dataclass

DISTRIBUTIONS = ("exponential", "deterministic", "uniform", "triangular")
PICKUP_MODES = ("shared", "per_window", "none")


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Configuration for one cafeteria simulation run.

    Rates and durations are explicit about their units: arrival rates are
    customers per hour, service means are seconds, and the planning horizon is
    minutes. The observation window is [warmup, duration]; customers who arrive
    before the warm-up are simulated but excluded from reported statistics.
    """

    arrival_rate_per_hour: float = 120.0
    duration_minutes: float = 120.0
    warmup_minutes: float = 10.0

    order_windows: int = 3
    order_mean_s: float = 75.0
    order_dist: str = "exponential"

    pickup_mode: str = "shared"
    pickup_servers: int = 2
    pickup_mean_s: float = 45.0
    pickup_dist: str = "exponential"

    max_order_queue: int | None = None
    max_pickup_queue: int | None = None
    order_patience_mean_s: float | None = None
    pickup_patience_mean_s: float | None = None

    seed: int = 42

    def __post_init__(self) -> None:
        if self.arrival_rate_per_hour <= 0:
            raise ValueError("arrival_rate_per_hour must be positive")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        if self.warmup_minutes < 0:
            raise ValueError("warmup_minutes must be non-negative")
        if self.warmup_minutes >= self.duration_minutes:
            raise ValueError("warmup_minutes must be shorter than duration_minutes")
        if not isinstance(self.order_windows, int) or self.order_windows < 1:
            raise ValueError("order_windows must be an integer >= 1")
        if not isinstance(self.pickup_servers, int) or self.pickup_servers < 1:
            raise ValueError("pickup_servers must be an integer >= 1")
        if self.order_mean_s <= 0:
            raise ValueError("order_mean_s must be positive")
        if self.pickup_mean_s <= 0:
            raise ValueError("pickup_mean_s must be positive")
        if self.order_dist not in DISTRIBUTIONS:
            raise ValueError(f"order_dist must be one of {DISTRIBUTIONS}")
        if self.pickup_dist not in DISTRIBUTIONS:
            raise ValueError(f"pickup_dist must be one of {DISTRIBUTIONS}")
        if self.pickup_mode not in PICKUP_MODES:
            raise ValueError(f"pickup_mode must be one of {PICKUP_MODES}")
        if self.max_order_queue is not None and (
            not isinstance(self.max_order_queue, int) or self.max_order_queue < 0
        ):
            raise ValueError("max_order_queue must be None or an integer >= 0")
        if self.max_pickup_queue is not None and (
            not isinstance(self.max_pickup_queue, int) or self.max_pickup_queue < 0
        ):
            raise ValueError("max_pickup_queue must be None or an integer >= 0")
        if self.order_patience_mean_s is not None and self.order_patience_mean_s <= 0:
            raise ValueError("order_patience_mean_s must be None or positive")
        if self.pickup_patience_mean_s is not None and self.pickup_patience_mean_s <= 0:
            raise ValueError("pickup_patience_mean_s must be None or positive")
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")

    @property
    def duration_s(self) -> float:
        return self.duration_minutes * 60.0

    @property
    def warmup_s(self) -> float:
        return self.warmup_minutes * 60.0

    @property
    def effective_duration_s(self) -> float:
        return self.duration_s - self.warmup_s

    @property
    def effective_duration_hours(self) -> float:
        return self.effective_duration_s / 3600.0
