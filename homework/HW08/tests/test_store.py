import tempfile
import unittest
from pathlib import Path

from xfrescue.db import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_upsert_and_counts(self):
        self.store.upsert_forums([{"forumId": "1", "title": "General"}])
        self.store.upsert_threads(
            [{"threadId": "10", "forumId": "1", "title": "Hello", "postCount": 2}]
        )
        self.store.upsert_posts(
            [
                {"postId": "100", "threadId": "10", "postIndex": 1, "authorName": "A",
                 "contentHtml": "<p>hi</p>"},
                {"postId": "101", "threadId": "10", "postIndex": 2, "authorName": "B",
                 "contentHtml": "<p>there</p>"},
            ]
        )
        counts = self.store.counts()
        self.assertEqual(counts["threads"], 1)
        self.assertEqual(counts["posts"], 2)
        self.assertEqual(counts["forums"], 1)

    def test_asset_priority_zero_is_preserved(self):
        self.store.add_assets(
            [
                {"url": "https://x/a", "kind": "attachment", "priority": 0},
                {"url": "https://x/b", "kind": "image", "priority": 1},
            ]
        )
        pending = self.store.pending_assets()
        self.assertEqual(pending[0]["url"], "https://x/a")
        self.assertEqual(pending[0]["priority"], 0)

    def test_asset_lifecycle(self):
        self.store.add_assets([{"url": "https://x/a", "kind": "image", "priority": 1}])
        self.store.mark_asset("https://x/a", status="done", size=3, sha256="abc",
                              local_path="assets/a.png")
        self.assertEqual(self.store.counts()["assets_done"], 1)
        self.assertEqual(self.store.asset_map()["https://x/a"], "assets/a.png")
        self.store.reset_asset_errors()
        self.assertEqual(self.store.counts()["assets_done"], 1)

    def test_csv_export(self):
        self.store.add_assets([{"url": "https://x/a", "kind": "image"}])
        out = Path(self.tmp.name) / "assets.csv"
        self.store.export_assets_csv(out)
        text = out.read_text(encoding="utf-8-sig")
        self.assertIn("https://x/a", text)


if __name__ == "__main__":
    unittest.main()
