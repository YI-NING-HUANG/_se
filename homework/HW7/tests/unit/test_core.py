from __future__ import annotations

import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import Leaderboard, clean_name, valid_score


class CleanNameUnitTests(unittest.TestCase):
    def test_trims_and_collapses_spaces(self) -> None:
        self.assertEqual(clean_name("   Dino   Runner  "), "Dino Runner")

    def test_control_characters_become_spaces(self) -> None:
        self.assertEqual(clean_name("Ada\nLovelace"), "Ada Lovelace")
        self.assertEqual(clean_name("Ada\tLovelace"), "Ada Lovelace")
        self.assertEqual(clean_name("Ada\x00Lovelace"), "Ada Lovelace")

    def test_length_boundaries(self) -> None:
        self.assertEqual(clean_name("A"), "A")
        self.assertEqual(clean_name("字" * 16), "字" * 16)
        self.assertIsNone(clean_name("字" * 17))
        self.assertIsNone(clean_name(""))

    def test_only_whitespace_is_rejected(self) -> None:
        self.assertIsNone(clean_name("    "))
        self.assertIsNone(clean_name("\n\t\x00"))

    def test_non_string_is_rejected(self) -> None:
        for value in [None, 12, 1.5, True, [], {}]:
            with self.subTest(value=value):
                self.assertIsNone(clean_name(value))

    def test_unicode_name_is_kept(self) -> None:
        self.assertEqual(clean_name("小恐龍 🦖"), "小恐龍 🦖")


class ValidScoreUnitTests(unittest.TestCase):
    def test_valid_boundaries(self) -> None:
        self.assertEqual(valid_score(0), 0)
        self.assertEqual(valid_score(123), 123)
        self.assertEqual(valid_score(1_000_000), 1_000_000)

    def test_out_of_range_is_rejected(self) -> None:
        self.assertIsNone(valid_score(-1))
        self.assertIsNone(valid_score(1_000_001))

    def test_wrong_types_are_rejected(self) -> None:
        for value in [True, False, 1.0, "10", None, [], {}]:
            with self.subTest(value=value):
                self.assertIsNone(valid_score(value))


class LeaderboardUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "unit.db"
        self.board = Leaderboard(self.db_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_new_database_is_empty(self) -> None:
        self.assertEqual(self.board.top(10), [])
        self.assertEqual(
            self.board.stats(), {"games": 0, "best": 0, "average": 0.0}
        )

    def test_add_returns_record_and_rank(self) -> None:
        record, rank = self.board.add("Dino", 321)
        self.assertEqual(rank, 1)
        self.assertEqual(record["name"], "Dino")
        self.assertEqual(record["score"], 321)
        self.assertIsInstance(record["id"], int)
        self.assertRegex(
            record["created_at"], re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        )

    def test_rank_uses_score_and_insert_order(self) -> None:
        self.board.add("First", 100)
        _, second_rank = self.board.add("Second", 100)
        _, top_rank = self.board.add("Top", 200)
        _, bottom_rank = self.board.add("Bottom", 50)
        self.assertEqual(second_rank, 2)
        self.assertEqual(top_rank, 1)
        self.assertEqual(bottom_rank, 4)

    def test_top_orders_by_score_then_id(self) -> None:
        self.board.add("First", 100)
        self.board.add("Second", 100)
        self.board.add("Top", 200)
        names = [row["name"] for row in self.board.top(10)]
        self.assertEqual(names, ["Top", "First", "Second"])

    def test_top_respects_limit(self) -> None:
        for index in range(5):
            self.board.add(f"P{index}", index)
        self.assertEqual(len(self.board.top(2)), 2)
        self.assertEqual(len(self.board.top(10)), 5)

    def test_stats_aggregates_scores(self) -> None:
        self.board.add("A", 100)
        self.board.add("B", 200)
        self.board.add("C", 201)
        self.assertEqual(
            self.board.stats(),
            {"games": 3, "best": 201, "average": 167.0},
        )

    def test_persistence_across_instances(self) -> None:
        self.board.add("Saved", 77)
        reopened = Leaderboard(self.db_path)
        rows = reopened.top(10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Saved")
        self.assertEqual(rows[0]["score"], 77)

    def test_unicode_name_round_trip(self) -> None:
        self.board.add("小恐龍", 99)
        self.assertEqual(self.board.top(1)[0]["name"], "小恐龍")

    def test_rank_index_exists(self) -> None:
        with closing(sqlite3.connect(str(self.db_path))) as con:
            rows = con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name = ?",
                ("idx_scores_rank",),
            ).fetchall()
        self.assertEqual(rows, [("idx_scores_rank",)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
