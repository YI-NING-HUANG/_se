from __future__ import annotations

import unittest

from cafeteria_sim import max_overlap, percentile, wait_stats
from cafeteria_sim.metrics import interval_total


class MetricTests(unittest.TestCase):
    def test_percentile_uses_nearest_rank(self) -> None:
        values = [4.0, 1.0, 3.0, 2.0]
        self.assertEqual(percentile(values, 0), 1.0)
        self.assertEqual(percentile(values, 50), 2.0)
        self.assertEqual(percentile(values, 90), 4.0)
        self.assertEqual(percentile(values, 100), 4.0)
        self.assertEqual(percentile([], 95), 0.0)

    def test_percentile_rejects_invalid_p(self) -> None:
        with self.assertRaises(ValueError):
            percentile([1.0], 101)

    def test_wait_stats(self) -> None:
        stats = wait_stats([10.0, 20.0, 30.0, 40.0])
        self.assertEqual(stats["count"], 4)
        self.assertEqual(stats["mean_s"], 25.0)
        self.assertEqual(stats["p50_s"], 20.0)
        self.assertEqual(stats["p95_s"], 40.0)
        self.assertEqual(stats["max_s"], 40.0)

    def test_interval_total_clips_to_window(self) -> None:
        intervals = [(0.0, 10.0), (15.0, 25.0), (30.0, 40.0)]
        self.assertEqual(interval_total(intervals, 5.0, 35.0), 5.0 + 10.0 + 5.0)

    def test_max_overlap_handles_touching_intervals(self) -> None:
        intervals = [(0.0, 10.0), (10.0, 20.0), (5.0, 15.0)]
        self.assertEqual(max_overlap(intervals, 0.0, 20.0), 2)

    def test_max_overlap_clips_to_window(self) -> None:
        self.assertEqual(max_overlap([(0.0, 100.0)], 10.0, 20.0), 1)
        self.assertEqual(max_overlap([], 0.0, 10.0), 0)


if __name__ == "__main__":
    unittest.main()
