from __future__ import annotations

import unittest
from dataclasses import replace

from cafeteria_sim import SimulationConfig, optimize_staffing


class OptimizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = SimulationConfig(
            arrival_rate_per_hour=100,
            duration_minutes=60,
            warmup_minutes=5,
            order_windows=1,
            order_mean_s=60,
            order_dist="deterministic",
            pickup_mode="none",
            seed=3,
        )

    def test_finds_cheapest_feasible_plan(self) -> None:
        result = optimize_staffing(
            self.base,
            max_order_windows=5,
            order_window_cost=100,
            target_mean_wait_s=180,
            replications=1,
        )
        best = result.best
        self.assertIsNotNone(best)
        assert best is not None
        self.assertGreaterEqual(best.order_windows, 2)
        self.assertEqual(best.pickup_servers, 0)
        self.assertEqual(best.hourly_cost, best.order_windows * 100)
        self.assertTrue(best.feasible)
        self.assertLessEqual(best.metrics["total_wait_mean_s"], 180)

    def test_returns_none_when_target_is_infeasible(self) -> None:
        result = optimize_staffing(
            self.base,
            max_order_windows=2,
            order_window_cost=100,
            target_mean_wait_s=0.0,
            replications=1,
        )
        self.assertIsNone(result.best)
        self.assertTrue(all(not candidate.feasible for candidate in result.candidates))

    def test_per_window_pickup_is_priced_with_windows(self) -> None:
        config = replace(
            self.base,
            pickup_mode="per_window",
            pickup_servers=1,
            pickup_mean_s=30,
        )
        result = optimize_staffing(
            config,
            max_order_windows=3,
            max_pickup_servers=5,
            order_window_cost=100,
            pickup_server_cost=50,
            target_mean_wait_s=180,
            replications=1,
        )
        best = result.best
        self.assertIsNotNone(best)
        assert best is not None
        self.assertEqual(best.pickup_servers, best.order_windows)
        self.assertEqual(
            best.hourly_cost, best.order_windows * 100 + best.pickup_servers * 50
        )

    def test_p95_target_is_respected(self) -> None:
        result = optimize_staffing(
            self.base,
            max_order_windows=6,
            order_window_cost=100,
            target_p95_wait_s=600,
            replications=1,
        )
        best = result.best
        self.assertIsNotNone(best)
        assert best is not None
        self.assertLessEqual(best.metrics["total_wait_p95_s"], 600)

    def test_missing_target_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            optimize_staffing(self.base)

    def test_invalid_limits_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            optimize_staffing(self.base, max_order_windows=0, target_mean_wait_s=100)
        with self.assertRaises(ValueError):
            optimize_staffing(self.base, max_pickup_servers=0, target_mean_wait_s=100)
        with self.assertRaises(ValueError):
            optimize_staffing(
                self.base, order_window_cost=-1, target_mean_wait_s=100
            )


if __name__ == "__main__":
    unittest.main()
