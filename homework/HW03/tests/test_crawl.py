from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forumkeep.crawl import Crawler
from forumkeep.net import HttpClient
from forumkeep.policy import CrawlPolicy
from forumkeep.store import Store

from tests.fixture_forum import forum_routes
from tests.mock_server import MockForumServer


class CrawlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "archive"
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def _crawler(self, server, **policy_kwargs):
        policy = CrawlPolicy(seeds=[server.base + "/"], **policy_kwargs)
        client = HttpClient(delay=0, retries=0, robots="respect")
        crawler = Crawler(self.store, client, policy)
        crawler.add_seed(server.base + "/")
        return crawler, policy

    def test_crawl_discovers_pages_links_and_assets(self):
        with MockForumServer(forum_routes()) as server:
            crawler, _policy = self._crawler(server)
            summary = crawler.run()
            self.assertEqual(summary["fetched"], 5)
            self.assertGreaterEqual(summary["assets_found"], 7)
            self.assertNotIn("/private/secret.html", server.requests)
            self.assertIn("/robots.txt", server.requests)
            urls = {page["url"] for page in self.store.pages()}
            self.assertIn(server.base + "/", urls)
            self.assertIn(server.base + "/threads/one.html", urls)
            self.assertIn(server.base + "/threads/one.html?page=2", urls)
            self.assertEqual(self.store.queue_counts().get("blocked"), 1)
            redirect_page = self.store.get_page(server.base + "/redirect")
            self.assertIsNotNone(redirect_page)
            self.assertEqual(redirect_page["url"], server.base + "/forum.html")
            asset_urls = {asset["url"] for asset in self.store.assets()}
            self.assertIn(server.base + "/files/guide.zip", asset_urls)
            self.assertIn(server.base + "/attachments/guide.12/", asset_urls)
            self.assertIn(server.base + "/images/pic@2x.svg", asset_urls)
            links = self.store.conn.execute("SELECT COUNT(*) AS n FROM links").fetchone()["n"]
            self.assertGreater(links, 10)

    def test_second_run_is_idempotent(self):
        with MockForumServer(forum_routes()) as server:
            crawler, _policy = self._crawler(server)
            first = crawler.run()
            second = crawler.run()
            self.assertGreater(first["fetched"], 0)
            self.assertEqual(second["fetched"], 0)
            self.assertEqual(second["errors"], 0)

    def test_resume_with_max_pages(self):
        with MockForumServer(forum_routes()) as server:
            crawler, _policy = self._crawler(server)
            first = crawler.run(max_pages=2)
            self.assertEqual(first["fetched"], 2)
            self.assertGreater(sum(first["queue"].values()), 0)
            second = crawler.run()
            self.assertGreater(second["fetched"], 0)
            self.assertGreaterEqual(len(self.store.pages()), 4)

    def test_force_requeues_pages(self):
        with MockForumServer(forum_routes()) as server:
            crawler, _policy = self._crawler(server)
            crawler.run(max_pages=2)
            before = len(server.requests)
            crawler.run(max_pages=2, force=True)
            self.assertGreater(len(server.requests), before)


if __name__ == "__main__":
    unittest.main()
