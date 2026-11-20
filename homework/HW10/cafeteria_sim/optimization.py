from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .config import SimulationConfig
from .simulation import aggregate_results, run_replications


@dataclass(frozen=True)
class StaffingCandidate:
    order_windows: int
    pickup_servers: int
    hourly_cost: float
    feasible: bool
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_windows": self.order_windows,
            "pickup_servers": self.pickup_servers,
            "hourly_cost": self.hourly_cost,
            "feasible": self.feasible,
            "metrics": dict(self.metrics),
        }


@dataclass
class OptimizationResult:
    target_mean_wait_s: float | None
    target_p95_wait_s: float | None
    replications: int
    candidates: list[StaffingCandidate]

    @property
    def best(self) -> StaffingCandidate | None:
        feasible = [candidate for candidate in self.candidates if candidate.feasible]
        if not feasible:
            return None
        return min(
            feasible,
            key=lambda candidate: (
                candidate.hourly_cost,
                candidate.metrics["total_wait_mean_s"],
                candidate.metrics["total_wait_p95_s"],
            ),
        )

    def ranked(self, include_infeasible: bool = False) -> list[StaffingCandidate]:
        candidates = (
            list(self.candidates)
            if include_infeasible
            else [candidate for candidate in self.candidates if candidate.feasible]
        )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.hourly_cost,
                candidate.metrics["total_wait_mean_s"],
                candidate.metrics["total_wait_p95_s"],
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        best = self.best
        return {
            "target_mean_wait_s": self.target_mean_wait_s,
            "target_p95_wait_s": self.target_p95_wait_s,
            "replications": self.replications,
            "best": best.to_dict() if best else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def optimize_staffing(
    config: SimulationConfig,
    *,
    max_order_windows: int = 6,
    max_pickup_servers: int = 4,
    order_window_cost: float = 150.0,
    pickup_server_cost: float = 100.0,
    target_mean_wait_s: float | None = None,
    target_p95_wait_s: float | None = None,
    replications: int = 3,
) -> OptimizationResult:
    """Enumerate integer staffing plans and evaluate each plan by simulation.

    The objective is minimum hourly staffing cost. A plan is feasible when its
    simulated mean and/or p95 total waiting time meet the requested targets.
    For ``per_window`` pickup, each order window owns one pickup line, so the
    pickup count follows the window count. For ``none``, only order windows
    are staffed.
    """

    if target_mean_wait_s is None and target_p95_wait_s is None:
        raise ValueError("provide at least one of target_mean_wait_s or target_p95_wait_s")
    if target_mean_wait_s is not None and target_mean_wait_s < 0:
        raise ValueError("target_mean_wait_s must be non-negative")
    if target_p95_wait_s is not None and target_p95_wait_s < 0:
        raise ValueError("target_p95_wait_s must be non-negative")
    if not isinstance(max_order_windows, int) or max_order_windows < 1:
        raise ValueError("max_order_windows must be an integer >= 1")
    if not isinstance(max_pickup_servers, int) or max_pickup_servers < 1:
        raise ValueError("max_pickup_servers must be an integer >= 1")
    if order_window_cost < 0 or pickup_server_cost < 0:
        raise ValueError("costs must be non-negative")

    candidates: list[StaffingCandidate] = []
    for windows in range(1, max_order_windows + 1):
        if config.pickup_mode == "shared":
            server_options = list(range(1, max_pickup_servers + 1))
        elif config.pickup_mode == "per_window":
            server_options = [windows]
        else:
            server_options = [0]

        for servers in server_options:
            scenario_config = replace(
                config,
                order_windows=windows,
                pickup_servers=servers if servers >= 1 else config.pickup_servers,
            )
            aggregated = aggregate_results(
                run_replications(scenario_config, replications)
            )
            metrics = aggregated.metrics
            feasible = True
            if target_mean_wait_s is not None:
                feasible = feasible and metrics["total_wait_mean_s"] <= target_mean_wait_s
            if target_p95_wait_s is not None:
                feasible = feasible and metrics["total_wait_p95_s"] <= target_p95_wait_s

            cost = windows * order_window_cost + servers * pickup_server_cost
            candidates.append(
                StaffingCandidate(
                    order_windows=windows,
                    pickup_servers=servers,
                    hourly_cost=float(cost),
                    feasible=feasible,
                    metrics=metrics,
                )
            )

    return OptimizationResult(
        target_mean_wait_s=target_mean_wait_s,
        target_p95_wait_s=target_p95_wait_s,
        replications=replications,
        candidates=candidates,
    )
