from __future__ import annotations

import unittest
from dataclasses import replace

from cafeteria_sim import SimulationConfig


class ConfigTests(unittest.TestCase):
    def test_defaults_are_valid(self) -> None:
        config = SimulationConfig()
        self.assertEqual(config.order_windows, 3)
        self.assertGreater(config.effective_duration_s, 0)

    def test_properties_convert_units(self) -> None:
        config = SimulationConfig(duration_minutes=90, warmup_minutes=5)
        self.assertEqual(config.duration_s, 5400)
        self.assertEqual(config.warmup_s, 300)
        self.assertEqual(config.effective_duration_s, 5100)
        self.assertAlmostEqual(config.effective_duration_hours, 5100 / 3600)

    def test_invalid_values_are_rejected(self) -> None:
        invalid = [
            {"arrival_rate_per_hour": 0},
            {"duration_minutes": 0},
            {"warmup_minutes": -1},
            {"warmup_minutes": 120},
            {"order_windows": 0},
            {"pickup_servers": 0},
            {"order_mean_s": 0},
            {"pickup_mean_s": 0},
            {"order_dist": "normal"},
            {"pickup_dist": "normal"},
            {"pickup_mode": "separate"},
            {"max_order_queue": -1},
            {"max_pickup_queue": -1},
            {"order_patience_mean_s": 0},
            {"pickup_patience_mean_s": 0},
            {"seed": -1},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(SimulationConfig(), **changes)

    def test_none_pickup_is_valid(self) -> None:
        config = SimulationConfig(pickup_mode="none")
        self.assertEqual(config.pickup_mode, "none")


if __name__ == "__main__":
    unittest.main()
