from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from forumkeep.build import build_site, page_site_path
from forumkeep.crawl import Crawler
from forumkeep.download import Downloader
from forumkeep.net import HttpClient
from forumkeep.policy import CrawlPolicy
from forumkeep.store import Store
from forumkeep.verify import verify_archive

from tests.fixture_forum import forum_routes
from tests.mock_server import MockForumServer


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "archive"
        self.store = Store(self.root)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def _archive(self, server):
        policy = CrawlPolicy(seeds=[server.base + "/"])
        client = HttpClient(delay=0, retries=0, robots="respect")
        crawler = Crawler(self.store, client, policy)
        crawler.add_seed(server.base + "/")
        crawler.run()
        downloader = Downloader(self.store, client, policy)
        return policy, downloader

    def test_download_and_offline_build(self):
        with MockForumServer(forum_routes()) as server:
            _policy, downloader = self._archive(server)
            summary = downloader.run(max_bytes=10 * 1024 * 1024)
            self.assertEqual(summary["failed"], 0)
            self.assertEqual(summary["skipped"], 0)
            self.assertGreaterEqual(summary["downloaded"], 8)
            self.assertEqual(self.store.assets("pending"), [])
            self.assertEqual(
                {asset["kind"] for asset in self.store.assets("done")}
                >= {"image", "archive", "stylesheet", "attachment", "document"},
                True,
            )
            result = build_site(self.store, strip_scripts=True)
            self.assertEqual(result["pages"], 5)
            site = self.root / "site"
            self.assertTrue((site / "index.html").exists())
            manifest = json.loads((site / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["pages"]), 5)
            one_rel = page_site_path(server.base + "/threads/one.html")
            one = (site / one_rel).read_text(encoding="utf-8")
            self.assertNotIn("<script", one)
            self.assertNotIn("onload", one)
            self.assertIn("ForumKeep", one)
            self.assertIn("../../assets/", one)
            hrefs = re.findall(r'href="([^"]+)"', one)
            self.assertTrue(any("the-guide" in href for href in hrefs))
            for href in hrefs:
                if href.startswith(("http://", "https://", "#")):
                    continue
                target = (site / one_rel).parent / href.split("#")[0]
                self.assertTrue(target.exists(), href)
            home = (site / page_site_path(server.base + "/")).read_text(encoding="utf-8")
            self.assertIn(server.base + "/private/secret.html", home)
            css_files = list((site / "assets").rglob("*.css"))
            self.assertTrue(css_files)
            css_text = "\n".join(path.read_text(encoding="utf-8") for path in css_files)
            self.assertIn("url(\"../", css_text)
            self.assertNotIn("/images/bg.svg", css_text)
            self.assertTrue((site / "search-index.js").exists())
            summary = verify_archive(self.store)
            self.assertTrue(summary["ok"])

    def test_hash_failure_and_fix(self):
        with MockForumServer(forum_routes()) as server:
            _policy, downloader = self._archive(server)
            downloader.run(max_bytes=10 * 1024 * 1024)
            asset = [row for row in self.store.assets("done") if row["kind"] == "archive"][0]
            blob = self.root / asset["local_path"]
            blob.write_bytes(b"corrupted")
            result = verify_archive(self.store)
            self.assertFalse(result["ok"])
            self.assertTrue(result["asset_issues"])
            fix = verify_archive(self.store, fix=True)
            self.assertFalse(fix["ok"])
            self.assertEqual(self.store.get_asset(asset["url"])["status"], "pending")
            downloader.run(max_bytes=10 * 1024 * 1024)
            self.assertEqual(self.store.get_asset(asset["url"])["status"], "done")
            self.assertTrue(verify_archive(self.store)["ok"])

    def test_page_hash_failure_and_fix(self):
        with MockForumServer(forum_routes()) as server:
            _policy, downloader = self._archive(server)
            downloader.run(max_bytes=10 * 1024 * 1024)
            page = self.store.pages()[0]
            raw = self.root / page["raw_path"]
            raw.write_text("<html>broken</html>", encoding="utf-8")
            result = verify_archive(self.store)
            self.assertFalse(result["ok"])
            verify_archive(self.store, fix=True)
            self.assertEqual(self.store.next_queued_page()["status"], "pending")


if __name__ == "__main__":
    unittest.main()
