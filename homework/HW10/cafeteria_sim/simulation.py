from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field, replace
from typing import Any

import simpy

from .config import SimulationConfig
from .distributions import Sampler, make_sampler
from .metrics import interval_total, max_overlap, wait_stats


@dataclass(slots=True)
class Customer:
    customer_id: int
    arrival_time: float
    window: int | None = None
    order_queue_enter: float | None = None
    order_start: float | None = None
    order_end: float | None = None
    pickup_queue_enter: float | None = None
    pickup_start: float | None = None
    pickup_end: float | None = None
    departure_time: float | None = None
    completed: bool = False
    balked: bool = False
    reneged_order: bool = False
    balked_pickup: bool = False
    reneged_pickup: bool = False

    @property
    def order_wait_s(self) -> float:
        if self.order_queue_enter is None or self.order_start is None:
            return 0.0
        return self.order_start - self.order_queue_enter

    @property
    def pickup_wait_s(self) -> float:
        if self.pickup_queue_enter is None or self.pickup_start is None:
            return 0.0
        return self.pickup_start - self.pickup_queue_enter

    @property
    def total_wait_s(self) -> float:
        return self.order_wait_s + self.pickup_wait_s

    @property
    def system_time_s(self) -> float:
        if self.departure_time is None:
            return 0.0
        return self.departure_time - self.arrival_time


@dataclass
class SimulationResult:
    config: SimulationConfig
    customers: list[Customer]
    metrics: dict[str, float]
    order_queue_intervals: list[list[tuple[float, float]]] = field(repr=False)
    pickup_queue_intervals: list[list[tuple[float, float]]] = field(repr=False)
    order_service_intervals: list[list[tuple[float, float]]] = field(repr=False)
    pickup_service_intervals: list[list[tuple[float, float]]] = field(repr=False)
    replications: int = 1

    def to_dict(self, include_customers: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "config": asdict(self.config),
            "metrics": dict(self.metrics),
            "replications": self.replications,
        }
        if include_customers:
            data["customers"] = [asdict(customer) for customer in self.customers]
        return data


@dataclass
class ScenarioResult:
    label: str
    config: SimulationConfig
    metrics: dict[str, float]
    replications: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "config": asdict(self.config),
            "metrics": dict(self.metrics),
            "replications": self.replications,
        }


class _CafeteriaSimulation:
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        self.env = simpy.Environment()
        self.customers: list[Customer] = []

        self.order_samplers: list[Sampler] = [
            make_sampler(config.order_dist, config.order_mean_s, self.rng)
            for _ in range(config.order_windows)
        ]
        self.pickup_sampler = make_sampler(config.pickup_dist, config.pickup_mean_s, self.rng)

        self.windows = [
            simpy.Resource(self.env, capacity=1) for _ in range(config.order_windows)
        ]
        if config.pickup_mode == "shared":
            self.pickups = [
                simpy.Resource(self.env, capacity=config.pickup_servers)
            ]
        elif config.pickup_mode == "per_window":
            self.pickups = [
                simpy.Resource(self.env, capacity=1) for _ in range(config.order_windows)
            ]
        else:
            self.pickups = []

        self.order_queue_intervals: list[list[tuple[float, float]]] = [
            [] for _ in self.windows
        ]
        self.pickup_queue_intervals: list[list[tuple[float, float]]] = [
            [] for _ in self.pickups
        ]
        self.order_service_intervals: list[list[tuple[float, float]]] = [
            [] for _ in self.windows
        ]
        self.pickup_service_intervals: list[list[tuple[float, float]]] = [
            [] for _ in self.pickups
        ]

    def run(self) -> SimulationResult:
        self.env.process(self._arrivals())
        self.env.run()

        metrics = _summarize(
            self.config,
            self.customers,
            self.order_queue_intervals,
            self.pickup_queue_intervals,
            self.order_service_intervals,
            self.pickup_service_intervals,
        )
        return SimulationResult(
            config=self.config,
            customers=self.customers,
            metrics=metrics,
            order_queue_intervals=self.order_queue_intervals,
            pickup_queue_intervals=self.pickup_queue_intervals,
            order_service_intervals=self.order_service_intervals,
            pickup_service_intervals=self.pickup_service_intervals,
        )

    def _arrivals(self):
        interarrival_rate = self.config.arrival_rate_per_hour / 3600.0
        customer_id = 0
        while True:
            yield self.env.timeout(self.rng.expovariate(interarrival_rate))
            if self.env.now >= self.config.duration_s:
                return
            customer_id += 1
            customer = Customer(customer_id=customer_id, arrival_time=self.env.now)
            self.customers.append(customer)
            self.env.process(self._serve_customer(customer))

    def _choose_order_window(self, customer: Customer) -> int | None:
        queue_lengths = [len(window.queue) for window in self.windows]
        shortest = min(queue_lengths)
        candidates = [
            index for index, length in enumerate(queue_lengths) if length == shortest
        ]
        index = self.rng.choice(candidates)
        window = self.windows[index]
        available = window.count < window.capacity and not window.queue
        if (
            self.config.max_order_queue is not None
            and not available
            and len(window.queue) >= self.config.max_order_queue
        ):
            customer.balked = True
            customer.departure_time = self.env.now
            return None
        return index

    def _acquire(self, request: simpy.Request, patience_mean_s: float | None):
        if patience_mean_s is None:
            yield request
            return True
        timeout = self.env.timeout(self.rng.expovariate(1.0 / patience_mean_s))
        result = yield request | timeout
        if request in result:
            return True
        if request.triggered:
            return True
        request.cancel()
        return False

    def _serve_customer(self, customer: Customer):
        window_index = self._choose_order_window(customer)
        if window_index is None:
            return

        customer.window = window_index
        window = self.windows[window_index]
        request = window.request()
        queue_enter = self.env.now
        customer.order_queue_enter = queue_enter

        acquired = yield from self._acquire(request, self.config.order_patience_mean_s)
        if not acquired:
            customer.reneged_order = True
            customer.departure_time = self.env.now
            self.order_queue_intervals[window_index].append(
                (queue_enter, customer.departure_time)
            )
            return

        order_start = self.env.now
        customer.order_start = order_start
        self.order_queue_intervals[window_index].append((queue_enter, order_start))
        service_time = self.order_samplers[window_index]()
        try:
            yield self.env.timeout(service_time)
        finally:
            window.release(request)

        customer.order_end = self.env.now
        self.order_service_intervals[window_index].append(
            (order_start, customer.order_end)
        )

        if self.config.pickup_mode == "none":
            customer.completed = True
            customer.departure_time = self.env.now
            return

        pickup_index = 0 if self.config.pickup_mode == "shared" else window_index
        pickup = self.pickups[pickup_index]
        available = pickup.count < pickup.capacity and not pickup.queue
        if (
            self.config.max_pickup_queue is not None
            and not available
            and len(pickup.queue) >= self.config.max_pickup_queue
        ):
            customer.balked_pickup = True
            customer.departure_time = self.env.now
            return

        pickup_request = pickup.request()
        pickup_queue_enter = self.env.now
        customer.pickup_queue_enter = pickup_queue_enter

        pickup_acquired = yield from self._acquire(
            pickup_request, self.config.pickup_patience_mean_s
        )
        if not pickup_acquired:
            customer.reneged_pickup = True
            customer.departure_time = self.env.now
            self.pickup_queue_intervals[pickup_index].append(
                (pickup_queue_enter, customer.departure_time)
            )
            return

        pickup_start = self.env.now
        customer.pickup_start = pickup_start
        self.pickup_queue_intervals[pickup_index].append(
            (pickup_queue_enter, pickup_start)
        )
        pickup_service = self.pickup_sampler()
        try:
            yield self.env.timeout(pickup_service)
        finally:
            pickup.release(pickup_request)

        customer.pickup_end = self.env.now
        customer.departure_time = self.env.now
        customer.completed = True
        self.pickup_service_intervals[pickup_index].append(
            (pickup_start, customer.pickup_end)
        )


def _served_in_window(customers: list[Customer], config: SimulationConfig) -> list[Customer]:
    return [
        customer
        for customer in customers
        if config.warmup_s <= customer.arrival_time < config.duration_s
        and customer.completed
    ]


def _add_wait_metrics(
    metrics: dict[str, float], prefix: str, values: list[float]
) -> None:
    stats = wait_stats(values)
    for key in ("mean", "p50", "p90", "p95", "max"):
        metrics[f"{prefix}_{key}_s"] = stats[f"{key}_s"]


def _summarize(
    config: SimulationConfig,
    customers: list[Customer],
    order_queue_intervals: list[list[tuple[float, float]]],
    pickup_queue_intervals: list[list[tuple[float, float]]],
    order_service_intervals: list[list[tuple[float, float]]],
    pickup_service_intervals: list[list[tuple[float, float]]],
) -> dict[str, float]:
    t0 = config.warmup_s
    t1 = config.duration_s
    effective_s = config.effective_duration_s
    effective_hours = config.effective_duration_hours
    in_window = [
        customer
        for customer in customers
        if t0 <= customer.arrival_time < t1
    ]
    served = [customer for customer in in_window if customer.completed]
    departures = [
        customer
        for customer in customers
        if customer.completed
        and customer.departure_time is not None
        and t0 <= customer.departure_time < t1
    ]

    arrivals = len(in_window)
    served_count = len(served)
    departure_count = len(departures)
    balked = sum(1 for customer in in_window if customer.balked)
    balked_pickup = sum(1 for customer in in_window if customer.balked_pickup)
    reneged_order = sum(1 for customer in in_window if customer.reneged_order)
    reneged_pickup = sum(1 for customer in in_window if customer.reneged_pickup)

    metrics: dict[str, float] = {
        "arrivals": float(arrivals),
        "served": float(served_count),
        "departures": float(departure_count),
        "abandoned": float(arrivals - served_count),
        "balked": float(balked),
        "balked_pickup": float(balked_pickup),
        "reneged_order": float(reneged_order),
        "reneged_pickup": float(reneged_pickup),
        "completion_rate": served_count / arrivals if arrivals else 0.0,
        "throughput_per_hour": departure_count / effective_hours,
        "observed_arrival_rate_per_hour": arrivals / effective_hours,
    }

    _add_wait_metrics(
        metrics, "order_wait", [customer.order_wait_s for customer in served]
    )
    _add_wait_metrics(
        metrics, "pickup_wait", [customer.pickup_wait_s for customer in served]
    )
    _add_wait_metrics(
        metrics, "total_wait", [customer.total_wait_s for customer in served]
    )
    _add_wait_metrics(
        metrics, "system_time", [customer.system_time_s for customer in served]
    )

    order_busy = sum(
        interval_total(intervals, t0, t1) for intervals in order_service_intervals
    )
    order_capacity = effective_s * config.order_windows
    metrics["order_utilization"] = order_busy / order_capacity if order_capacity else 0.0

    if config.pickup_mode == "shared":
        pickup_capacity_count = config.pickup_servers
    elif config.pickup_mode == "per_window":
        pickup_capacity_count = config.order_windows
    else:
        pickup_capacity_count = 0
    pickup_busy = sum(
        interval_total(intervals, t0, t1) for intervals in pickup_service_intervals
    )
    pickup_capacity = effective_s * pickup_capacity_count
    metrics["pickup_utilization"] = (
        pickup_busy / pickup_capacity if pickup_capacity else 0.0
    )

    order_queue_total = sum(
        interval_total(intervals, t0, t1) for intervals in order_queue_intervals
    )
    metrics["avg_order_queue"] = order_queue_total / effective_s
    metrics["avg_order_queue_per_window"] = (
        metrics["avg_order_queue"] / config.order_windows
    )
    metrics["max_order_queue"] = float(
        max(
            (
                max_overlap(intervals, t0, t1)
                for intervals in order_queue_intervals
            ),
            default=0,
        )
    )

    pickup_queue_total = sum(
        interval_total(intervals, t0, t1) for intervals in pickup_queue_intervals
    )
    metrics["avg_pickup_queue"] = pickup_queue_total / effective_s
    metrics["max_pickup_queue"] = float(
        max(
            (
                max_overlap(intervals, t0, t1)
                for intervals in pickup_queue_intervals
            ),
            default=0,
        )
    )

    return metrics


def run_simulation(config: SimulationConfig) -> SimulationResult:
    """Run one stochastic simulation with the configured seed."""

    return _CafeteriaSimulation(config).run()


def run_replications(
    config: SimulationConfig, replications: int = 3
) -> list[SimulationResult]:
    """Run independent replications using seeds seed, seed+1, ..."""

    if not isinstance(replications, int) or replications < 1:
        raise ValueError("replications must be an integer >= 1")
    return [
        run_simulation(replace(config, seed=config.seed + index))
        for index in range(replications)
    ]


def aggregate_results(results: list[SimulationResult]) -> SimulationResult:
    """Pool replications into one result; wait times are pooled per customer."""

    if not results:
        raise ValueError("results must not be empty")
    config = results[0].config
    replications = len(results)
    customers = [customer for result in results for customer in result.customers]
    served = [
        customer
        for result in results
        for customer in _served_in_window(result.customers, result.config)
    ]

    count_keys = (
        "arrivals",
        "served",
        "departures",
        "abandoned",
        "balked",
        "balked_pickup",
        "reneged_order",
        "reneged_pickup",
    )
    metrics: dict[str, float] = {
        key: sum(result.metrics[key] for result in results) for key in count_keys
    }
    total_arrivals = metrics["arrivals"]
    total_served = metrics["served"]
    total_departures = metrics["departures"]
    total_hours = config.effective_duration_hours * replications
    metrics["completion_rate"] = (
        total_served / total_arrivals if total_arrivals else 0.0
    )
    metrics["throughput_per_hour"] = total_departures / total_hours
    metrics["observed_arrival_rate_per_hour"] = total_arrivals / total_hours

    mean_keys = (
        "order_utilization",
        "pickup_utilization",
        "avg_order_queue",
        "avg_order_queue_per_window",
        "avg_pickup_queue",
    )
    for key in mean_keys:
        metrics[key] = sum(result.metrics[key] for result in results) / replications

    metrics["max_order_queue"] = max(
        result.metrics["max_order_queue"] for result in results
    )
    metrics["max_pickup_queue"] = max(
        result.metrics["max_pickup_queue"] for result in results
    )

    _add_wait_metrics(
        metrics, "order_wait", [customer.order_wait_s for customer in served]
    )
    _add_wait_metrics(
        metrics, "pickup_wait", [customer.pickup_wait_s for customer in served]
    )
    _add_wait_metrics(
        metrics, "total_wait", [customer.total_wait_s for customer in served]
    )
    _add_wait_metrics(
        metrics, "system_time", [customer.system_time_s for customer in served]
    )

    return SimulationResult(
        config=config,
        customers=customers,
        metrics=metrics,
        order_queue_intervals=[],
        pickup_queue_intervals=[],
        order_service_intervals=[],
        pickup_service_intervals=[],
        replications=replications,
    )


def compare_windows(
    config: SimulationConfig,
    window_counts: list[int] | None = None,
    replications: int = 3,
) -> list[ScenarioResult]:
    """Compare staffing levels using common random numbers across scenarios."""

    if window_counts is None:
        window_counts = [1, 2, 3, 4, 5]
    unique_counts = list(dict.fromkeys(window_counts))
    if not unique_counts:
        raise ValueError("window_counts must not be empty")
    if any(not isinstance(count, int) or count < 1 for count in unique_counts):
        raise ValueError("every window count must be an integer >= 1")

    scenarios: list[ScenarioResult] = []
    for count in unique_counts:
        scenario_config = replace(config, order_windows=count)
        aggregated = aggregate_results(
            run_replications(scenario_config, replications)
        )
        scenarios.append(
            ScenarioResult(
                label=f"{count} window{'s' if count != 1 else ''}",
                config=scenario_config,
                metrics=aggregated.metrics,
                replications=replications,
            )
        )
    return scenarios
