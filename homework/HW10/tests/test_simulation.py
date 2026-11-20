from __future__ import annotations

import unittest
from dataclasses import replace

from cafeteria_sim import (
    SimulationConfig,
    aggregate_results,
    compare_windows,
    run_replications,
    run_simulation,
)


class SimulationTests(unittest.TestCase):
    def test_same_seed_is_reproducible(self) -> None:
        config = SimulationConfig(
            arrival_rate_per_hour=90,
            duration_minutes=30,
            warmup_minutes=5,
            order_windows=2,
            order_mean_s=40,
            pickup_mode="shared",
            pickup_servers=2,
            pickup_mean_s=20,
            seed=123,
        )
        first = run_simulation(config)
        second = run_simulation(config)
        self.assertEqual(first.metrics, second.metrics)
        self.assertEqual(len(first.customers), len(second.customers))

    def test_low_load_serves_everyone(self) -> None:
        config = SimulationConfig(
            arrival_rate_per_hour=30,
            duration_minutes=30,
            warmup_minutes=0,
            order_windows=2,
            order_mean_s=20,
            order_dist="deterministic",
            pickup_mode="none",
            seed=5,
        )
        result = run_simulation(config)
        metrics = result.metrics
        self.assertEqual(metrics["arrivals"], metrics["served"])
        self.assertEqual(metrics["abandoned"], 0)
        self.assertEqual(metrics["pickup_utilization"], 0)
        self.assertLess(metrics["total_wait_mean_s"], 10)

    def test_warmup_customers_are_excluded_from_metrics(self) -> None:
        config = SimulationConfig(
            arrival_rate_per_hour=120,
            duration_minutes=30,
            warmup_minutes=5,
            order_windows=3,
            order_mean_s=30,
            pickup_mode="none",
            seed=11,
        )
        result = run_simulation(config)
        self.assertLess(result.metrics["arrivals"], len(result.customers))
        self.assertGreater(len(result.customers) - result.metrics["arrivals"], 0)

    def test_balking_when_queue_limit_is_zero(self) -> None:
        config = SimulationConfig(
            arrival_rate_per_hour=600,
            duration_minutes=30,
            warmup_minutes=0,
            order_windows=1,
            order_mean_s=60,
            order_dist="deterministic",
            pickup_mode="none",
            max_order_queue=0,
            seed=3,
        )
        result = run_simulation(config)
        metrics = result.metrics
        self.assertGreater(metrics["balked"], 0)
        self.assertEqual(metrics["max_order_queue"], 0)
        self.assertLess(metrics["served"], metrics["arrivals"])

    def test_reneging_when_patience_is_short(self) -> None:
        config = SimulationConfig(
            arrival_rate_per_hour=600,
            duration_minutes=30,
            warmup_minutes=0,
            order_windows=1,
            order_mean_s=60,
            order_dist="deterministic",
            pickup_mode="none",
            order_patience_mean_s=5,
            seed=4,
        )
        result = run_simulation(config)
        self.assertGreater(result.metrics["reneged_order"], 0)
        self.assertLess(result.metrics["served"], result.metrics["arrivals"])

    def test_more_windows_reduce_waiting(self) -> None:
        base = SimulationConfig(
            arrival_rate_per_hour=120,
            duration_minutes=60,
            warmup_minutes=0,
            order_windows=2,
            order_mean_s=90,
            order_dist="deterministic",
            pickup_mode="none",
            seed=8,
        )
        few = aggregate_results(run_replications(base, 2))
        many = aggregate_results(
            run_replications(replace(base, order_windows=6), 2)
        )
        self.assertLess(
            many.metrics["total_wait_mean_s"], few.metrics["total_wait_mean_s"]
        )
        self.assertLess(
            many.metrics["total_wait_p95_s"], few.metrics["total_wait_p95_s"]
        )
        self.assertLess(
            many.metrics["avg_order_queue"], few.metrics["avg_order_queue"]
        )

    def test_compare_windows_uses_common_seeds(self) -> None:
        base = SimulationConfig(
            arrival_rate_per_hour=90,
            duration_minutes=30,
            warmup_minutes=5,
            order_windows=2,
            order_mean_s=40,
            pickup_mode="shared",
            pickup_servers=2,
            pickup_mean_s=20,
            seed=21,
        )
        scenarios = compare_windows(base, [2, 3], replications=2)
        self.assertEqual(len(scenarios), 2)
        self.assertEqual([s.config.order_windows for s in scenarios], [2, 3])
        self.assertEqual(scenarios[0].replications, 2)
        self.assertIn("total_wait_mean_s", scenarios[0].metrics)

    def test_pickup_modes(self) -> None:
        base = SimulationConfig(
            arrival_rate_per_hour=60,
            duration_minutes=30,
            warmup_minutes=0,
            order_windows=2,
            order_mean_s=20,
            order_dist="deterministic",
            pickup_servers=2,
            pickup_mean_s=10,
            pickup_dist="deterministic",
            seed=9,
        )
        shared = run_simulation(replace(base, pickup_mode="shared"))
        per_window = run_simulation(replace(base, pickup_mode="per_window"))
        none = run_simulation(replace(base, pickup_mode="none"))

        self.assertGreater(shared.metrics["served"], 0)
        self.assertGreater(shared.metrics["pickup_utilization"], 0)
        self.assertGreater(per_window.metrics["pickup_utilization"], 0)
        self.assertEqual(none.metrics["pickup_utilization"], 0)
        self.assertEqual(none.metrics["pickup_wait_mean_s"], 0)

    def test_aggregate_replications(self) -> None:
        config = SimulationConfig(
            arrival_rate_per_hour=90,
            duration_minutes=30,
            warmup_minutes=5,
            order_windows=3,
            order_mean_s=30,
            pickup_mode="none",
            seed=13,
        )
        results = run_replications(config, 3)
        self.assertEqual(len(results), 3)
        self.assertEqual(
            [result.config.seed for result in results], [13, 14, 15]
        )
        aggregated = aggregate_results(results)
        self.assertEqual(aggregated.replications, 3)
        self.assertEqual(
            aggregated.metrics["arrivals"],
            sum(result.metrics["arrivals"] for result in results),
        )
        self.assertIn("total_wait_p95_s", aggregated.metrics)

    def test_empty_aggregate_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            aggregate_results([])

    def test_invalid_replication_count_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_replications(SimulationConfig(), 0)


if __name__ == "__main__":
    unittest.main()
