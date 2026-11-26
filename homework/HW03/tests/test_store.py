from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from forumkeep.store import Store
from forumkeep.util import utc_now


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "archive"
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_queue_and_page(self):
        self.store.add_seed("https://forum.example/")
        self.assertTrue(self.store.enqueue_page("https://forum.example/", priority=1))
        self.assertFalse(self.store.enqueue_page("https://forum.example/", priority=1))
        row = self.store.next_queued_page()
        self.assertEqual(row["url"], "https://forum.example/")
        self.store.mark_queue_working(row["url"])
        self.store.upsert_page({
            "url": row["url"],
            "final_url": row["url"],
            "depth": 0,
            "kind": "index",
            "title": "Home",
            "size": 10,
            "sha256": "a" * 64,
            "raw_path": "raw/pages/x.html",
            "text": "hello",
            "attempts": 1,
        })
        self.store.add_alias("http://forum.example/", "https://forum.example/")
        self.store.mark_queue(row["url"], "done")
        self.assertEqual(self.store.next_queued_page(), None)
        self.assertEqual(self.store.get_page("http://forum.example/")["title"], "Home")
        self.assertEqual(len(self.store.pages()), 1)
        self.assertEqual(self.store.queue_counts()["done"], 1)

    def test_assets_and_counts(self):
        self.store.enqueue_asset(
            "https://forum.example/files/a.zip",
            page_url="https://forum.example/",
            kind="archive",
            priority=1,
        )
        asset = self.store.pending_assets()[0]
        self.assertEqual(asset["status"], "pending")
        self.store.mark_asset_done(
            asset["url"],
            final_url=asset["url"],
            http_status=200,
            content_type="application/zip",
            size=100,
            sha256="b" * 64,
            filename="a.zip",
            local_path="blobs/bb/a.zip",
        )
        self.assertEqual(self.store.counts()["assets"], 1)
        self.assertEqual(self.store.counts()["asset_bytes"], 100)
        self.assertEqual(self.store.pending_assets(), [])
        self.store.mark_asset_error(asset["url"], "bad hash")
        self.assertEqual(self.store.reset_asset_errors(), 1)
        self.assertEqual(len(self.store.pending_assets()), 1)

    def test_export(self):
        self.store.upsert_page({
            "url": "https://forum.example/",
            "final_url": "https://forum.example/",
            "depth": 0,
            "kind": "index",
            "title": "Home",
            "text": "hello",
        })
        self.store.enqueue_asset("https://forum.example/a.zip", kind="archive")
        jsonl = self.root / "exports" / "out.jsonl"
        count = self.store.export_jsonl(jsonl)
        self.assertGreaterEqual(count, 2)
        lines = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines()]
        self.assertEqual({line["type"] for line in lines}, {"page", "asset"})
        count = self.store.export_csv(self.root / "exports" / "csv")
        self.assertGreaterEqual(count, 2)
        self.assertTrue((self.root / "exports" / "csv" / "pages.csv").exists())

    def test_reopen_recovers_working_queue(self):
        self.store.add_seed("https://forum.example/")
        self.store.enqueue_page("https://forum.example/")
        self.store.mark_queue_working("https://forum.example/")
        self.store.close()
        self.store = Store(self.root)
        self.assertEqual(self.store.queue_counts().get("pending"), 1)

    def test_mark_page_bad_requeues(self):
        self.store.add_seed("https://forum.example/")
        self.store.enqueue_page("https://forum.example/")
        self.store.mark_queue("https://forum.example/", "done")
        self.store.upsert_page({"url": "https://forum.example/", "title": "Home"})
        self.store.mark_page_bad("https://forum.example/", "hash mismatch")
        self.assertEqual(self.store.get_page("https://forum.example/")["status"], "error")
        self.assertEqual(self.store.next_queued_page()["status"], "pending")


if __name__ == "__main__":
    unittest.main()
