import json
import tempfile
import unittest
from pathlib import Path

from xfrescue.build import Builder
from xfrescue.db import Store
from xfrescue.util import ensure_dir


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))
        self.store.upsert_forums([{"forumId": "1", "title": "General",
                                   "url": "https://forums.rpgmakerweb.com/forums/general.1/"}])
        self.store.upsert_threads([{
            "threadId": "10", "forumId": "1", "title": "A thread", "authorName": "Alice",
            "url": "https://forums.rpgmakerweb.com/threads/a-thread.10/",
            "createdAt": "2026-01-01", "pageCount": 1,
        }])
        self.store.upsert_posts([
            {
                "postId": "100", "threadId": "10", "postIndex": 1, "authorName": "Alice",
                "postedAt": "2026-01-01",
                "originalUrl": "https://forums.rpgmakerweb.com/threads/a-thread.10/#post-100",
                "contentHtml": '<div class="bbWrapper">Hello <img src="/data/attachments/1/pic.png">'
                               '<script>alert(1)</script></div>',
                "contentText": "Hello",
            },
            {
                "postId": "101", "threadId": "10", "postIndex": 2, "authorName": "Bob",
                "contentHtml": "<p>Second</p>", "contentText": "Second",
            },
        ])
        self.asset_url = "https://forums.rpgmakerweb.com/data/attachments/1/pic.png"
        self.store.add_assets([{
            "url": self.asset_url, "kind": "attachment", "priority": 0,
            "thread_id": "10", "post_id": "100",
        }])
        local = Path("assets/forum/forums.rpgmakerweb.com/data/attachments/1/pic.png")
        ensure_dir(self.store.root / local.parent)
        (self.store.root / local).write_bytes(b"PNG")
        self.store.mark_asset(
            self.asset_url, status="done", size=3, sha256="x",
            local_path=local.as_posix(), filename="pic.png",
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_build_site(self):
        builder = Builder(self.store, self.store.root, search_index=True)
        counts = builder.build()
        self.assertEqual(counts["posts"], 2)
        thread_html = (self.store.root / "site/threads/10/index.html").read_text(encoding="utf-8")
        self.assertIn("A thread", thread_html)
        self.assertIn("../../assets/forum/forums.rpgmakerweb.com/data/attachments/1/pic.png", thread_html)
        self.assertNotIn("<script>", thread_html)
        self.assertTrue((self.store.root / "site/forums/1/index.html").exists())
        self.assertTrue((self.store.root / "site/search.json").exists())
        self.assertTrue((self.store.root / "site/assets.csv").exists())
        index = (self.store.root / "site/index.html").read_text(encoding="utf-8")
        self.assertIn("RPG Maker Web forum archive", index)

    def test_search_indexes_posts(self):
        Builder(self.store, self.store.root, search_index=True).build()
        index = json.loads(
            (self.store.root / "site/search.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(index["threads"]), 1)
        self.assertEqual(len(index["posts"]), 2)
        first = next(p for p in index["posts"] if p["id"] == "100")
        self.assertEqual(first["text"], "Hello")
        self.assertIn("#post-100", first["url"])
        second = next(p for p in index["posts"] if p["id"] == "101")
        self.assertEqual(second["text"], "Second")
        self.assertEqual(second["author"], "Bob")

    def test_pagination(self):
        # Add enough posts to force a second page.
        for i in range(3, 60):
            self.store.upsert_posts([{
                "postId": str(100 + i), "threadId": "10", "postIndex": i,
                "authorName": "X", "contentHtml": f"<p>post {i}</p>",
            }])
        Builder(self.store, self.store.root, search_index=False).build()
        self.assertTrue((self.store.root / "site/threads/10/page-2.html").exists())


if __name__ == "__main__":
    unittest.main()
