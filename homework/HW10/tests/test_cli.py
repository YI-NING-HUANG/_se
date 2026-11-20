from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from cafeteria_sim.cli import main


class CliTests(unittest.TestCase):
    def test_run_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "run",
                    "--arrival-rate",
                    "60",
                    "--duration",
                    "30",
                    "--warmup",
                    "0",
                    "--order-windows",
                    "2",
                    "--order-mean",
                    "30",
                    "--pickup-mode",
                    "none",
                    "--json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["config"]["pickup_mode"], "none")
        self.assertGreater(payload["metrics"]["served"], 0)
        self.assertIn("total_wait_p95_s", payload["metrics"])

    def test_compare_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "compare",
                    "--arrival-rate",
                    "60",
                    "--duration",
                    "30",
                    "--warmup",
                    "0",
                    "--order-mean",
                    "30",
                    "--pickup-mode",
                    "none",
                    "--windows",
                    "1,2",
                    "--replications",
                    "1",
                    "--json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(len(payload["scenarios"]), 2)
        self.assertEqual(
            [scenario["config"]["order_windows"] for scenario in payload["scenarios"]],
            [1, 2],
        )

    def test_optimize_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "optimize",
                    "--arrival-rate",
                    "60",
                    "--duration",
                    "30",
                    "--warmup",
                    "0",
                    "--order-mean",
                    "30",
                    "--pickup-mode",
                    "none",
                    "--max-order-windows",
                    "3",
                    "--target-mean-wait",
                    "300",
                    "--replications",
                    "1",
                    "--json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertIsNotNone(payload["best"])
        self.assertEqual(payload["best"]["order_windows"], 1)

    def test_invalid_configuration_returns_error(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error):
            code = main(["run", "--arrival-rate", "-1", "--json"])
        self.assertEqual(code, 2)
        self.assertIn("arrival_rate_per_hour", error.getvalue())


if __name__ == "__main__":
    unittest.main()
