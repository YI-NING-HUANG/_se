from __future__ import annotations

import random
import unittest

from cafeteria_sim.distributions import make_sampler


class DistributionTests(unittest.TestCase):
    def test_deterministic_sampler(self) -> None:
        sampler = make_sampler("deterministic", 12.5, random.Random(1))
        self.assertEqual([sampler() for _ in range(5)], [12.5] * 5)

    def test_samplers_are_positive_and_centered(self) -> None:
        for name in ("exponential", "uniform", "triangular"):
            with self.subTest(distribution=name):
                rng = random.Random(7)
                sampler = make_sampler(name, 50.0, rng)
                samples = [sampler() for _ in range(20_000)]
                self.assertTrue(all(value > 0 for value in samples))
                self.assertAlmostEqual(sum(samples) / len(samples), 50.0, delta=1.5)

    def test_unknown_distribution_raises(self) -> None:
        with self.assertRaises(ValueError):
            make_sampler("normal", 10.0, random.Random(1))

    def test_non_positive_mean_raises(self) -> None:
        with self.assertRaises(ValueError):
            make_sampler("exponential", 0.0, random.Random(1))


if __name__ == "__main__":
    unittest.main()
