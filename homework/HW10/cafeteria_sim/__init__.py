"""Discrete-event simulation and staffing optimization for cafeteria queues."""

from .config import DISTRIBUTIONS, PICKUP_MODES, SimulationConfig
from .metrics import max_overlap, percentile, wait_stats
from .optimization import OptimizationResult, StaffingCandidate, optimize_staffing
from .simulation import (
    Customer,
    ScenarioResult,
    SimulationResult,
    aggregate_results,
    compare_windows,
    run_replications,
    run_simulation,
)

__all__ = [
    "DISTRIBUTIONS",
    "PICKUP_MODES",
    "Customer",
    "OptimizationResult",
    "ScenarioResult",
    "SimulationConfig",
    "SimulationResult",
    "StaffingCandidate",
    "aggregate_results",
    "compare_windows",
    "max_overlap",
    "optimize_staffing",
    "percentile",
    "run_replications",
    "run_simulation",
    "wait_stats",
]

__version__ = "0.1.1"
