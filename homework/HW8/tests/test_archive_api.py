import tempfile
import unittest
from pathlib import Path

from xfrescue.archive_api import ArchiveAPI
from xfrescue.db import Store
from xfrescue.net import HttpClient

from tests.mock_server import serve


def thread_page(page, posts):
    return {
        "ok": True,
        "thread": {
            "threadId": "123",
            "forumId": "1",
            "forumTitle": "General",
            "forumOriginalUrl": "https://forums.rpgmakerweb.com/forums/general.1/",
            "title": "Test thread",
            "originalUrl": "https://forums.rpgmakerweb.com/threads/test-thread.123/",
            "authorName": "Alice",
            "createdAt": "2026-01-01T00:00:00+0900",
        },
        "posts": posts,
        "page": page,
        "pageCount": 2,
        "postCount": 3,
    }


class ArchiveAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_discover_thread_pages_and_assets(self):
        routes = {
            "/api/thread/123?page=1": (
                200,
                {},
                thread_page(1, [
                    {
                        "postId": "1", "postIndex": 1, "authorName": "Alice",
                        "contentHtml": '<div class="bbWrapper"><a href="/attachments/a-png.9/">a</a>'
                                       '<img src="/data/attachments/1/pic.png">'
                                       '<a href="https://example.com/plugin.zip">zip</a></div>',
                        "contentText": "hello",
                        "originalUrl": "https://forums.rpgmakerweb.com/threads/test-thread.123/#post-1",
                    },
                    {
                        "postId": "2", "postIndex": 2, "authorName": "Bob",
                        "contentHtml": "<p>second</p>", "contentText": "second",
                    },
                ]),
            ),
            "/api/thread/123?page=2": (
                200,
                {},
                thread_page(2, [
                    {
                        "postId": "3", "postIndex": 3, "authorName": "Carol",
                        "contentHtml": "<p>third</p>", "contentText": "third",
                    }
                ]),
            ),
        }
        with serve(routes) as base:
            api = ArchiveAPI(HttpClient(delay=0, robots="ignore"), base=base,
                             root=self.store.root, save_raw=False)
            result = api.discover_thread(self.store, "123")
        self.assertEqual(result["posts"], 3)
        counts = self.store.counts()
        self.assertEqual(counts["posts"], 3)
        self.assertEqual(counts["forums"], 1)
        assets = {row["url"]: row for row in self.store.assets()}
        self.assertEqual(
            assets["https://forums.rpgmakerweb.com/attachments/a-png.9/"]["kind"],
            "attachment",
        )
        self.assertEqual(
            assets["https://forums.rpgmakerweb.com/attachments/a-png.9/"]["priority"], 0
        )
        self.assertIn("https://example.com/plugin.zip", assets)

    def test_discover_forum(self):
        routes = {
            "/api/forum/1/threads?page=1": (
                200,
                {},
                {
                    "ok": True,
                    "forum": {"forumId": "1", "title": "General",
                              "originalUrl": "https://forums.rpgmakerweb.com/forums/general.1/"},
                    "threads": [{"threadId": "123", "title": "Test thread",
                                 "originalUrl": "https://forums.rpgmakerweb.com/threads/test-thread.123/"}],
                    "page": 1, "pageCount": 1, "threadCount": 1,
                },
            ),
            "/api/thread/123?page=1": (200, {}, thread_page(1, [])),
            "/api/thread/123?page=2": (200, {}, thread_page(2, [])),
        }
        with serve(routes) as base:
            api = ArchiveAPI(HttpClient(delay=0, robots="ignore"), base=base,
                             root=self.store.root, save_raw=False)
            result = api.discover_forum(self.store, "1", with_posts=True)
        self.assertEqual(result["threads"], 1)
        self.assertEqual(self.store.counts()["threads"], 1)


if __name__ == "__main__":
    unittest.main()
