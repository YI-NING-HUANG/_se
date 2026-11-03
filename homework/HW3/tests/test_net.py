from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from forumkeep.net import FetchError, HttpClient, RobotsDenied, RobotsPolicy
from forumkeep.store import Store

from tests.fixture_forum import forum_routes
from tests.mock_server import MockForumServer, Route, html


class RobotsTests(unittest.TestCase):
    def test_parser_and_wildcards(self):
        policy = RobotsPolicy(
            """
            User-agent: other
            Disallow: /
            User-agent: ForumKeep
            Disallow: /private/
            Allow: /private/ok
            Disallow: /*.pdf$
            Crawl-delay: 1.5
            """,
            "ForumKeep/0.1",
        )
        self.assertTrue(policy.allowed("https://x.test/"))
        self.assertFalse(policy.allowed("https://x.test/private/a"))
        self.assertTrue(policy.allowed("https://x.test/private/ok/a"))
        self.assertFalse(policy.allowed("https://x.test/files/a.pdf"))
        self.assertTrue(policy.allowed("https://x.test/files/a.pdf?x=1"))
        self.assertEqual(policy.crawl_delay, 1.5)

    def test_wildcard_group(self):
        policy = RobotsPolicy("User-agent: *\nDisallow: /\n", "ForumKeep/0.1")
        self.assertFalse(policy.allowed("https://x.test/"))


class HttpClientTests(unittest.TestCase):
    def test_gzip_and_redirect(self):
        compressed = gzip.compress("<html><body>ok</body></html>".encode("utf-8"))
        routes = {
            "/robots.txt": Route(b"User-agent: *\nAllow: /\n", content_type="text/plain"),
            "/": Route(b"", status=302, headers={"Location": "/page"}),
            "/page": Route(compressed, headers={"Content-Encoding": "gzip"}),
        }
        with MockForumServer(routes) as server:
            client = HttpClient(delay=0, retries=0)
            response = client.get(server.base + "/")
            self.assertEqual(response.status, 200)
            self.assertEqual(response.url, server.base + "/page")
            self.assertIn(b"ok", response.body)

    def test_robots_blocks_before_request(self):
        routes = forum_routes()
        with MockForumServer(routes) as server:
            client = HttpClient(delay=0, retries=0)
            with self.assertRaises(RobotsDenied):
                client.get(server.base + "/private/secret.html")
            self.assertNotIn("/private/secret.html", server.requests)

    def test_download_to_file(self):
        routes = {
            "/robots.txt": Route(b"User-agent: *\nAllow: /\n", content_type="text/plain"),
            "/a.bin": Route(b"0123456789", content_type="application/octet-stream"),
        }
        with MockForumServer(routes) as server, tempfile.TemporaryDirectory() as temp:
            client = HttpClient(delay=0, retries=0)
            target = Path(temp) / "a.bin"
            response = client.download_to_file(
                server.base + "/a.bin", str(target), max_bytes=100
            )
            self.assertEqual(response.size, 10)
            self.assertEqual(target.read_bytes(), b"0123456789")

    def test_too_large(self):
        routes = {
            "/robots.txt": Route(b"User-agent: *\nAllow: /\n", content_type="text/plain"),
            "/big.bin": Route(b"x" * 100, content_type="application/octet-stream"),
        }
        with MockForumServer(routes) as server, tempfile.TemporaryDirectory() as temp:
            client = HttpClient(delay=0, retries=0)
            target = Path(temp) / "big.bin"
            with self.assertRaises(Exception):
                client.download_to_file(
                    server.base + "/big.bin", str(target), max_bytes=10
                )


if __name__ == "__main__":
    unittest.main()
