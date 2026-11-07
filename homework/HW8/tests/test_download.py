import hashlib
import tempfile
import unittest
from pathlib import Path

from xfrescue.db import Store
from xfrescue.download import Downloader
from xfrescue.net import HttpClient

from tests.mock_server import serve

PAYLOAD = b"PK\x03\x04" + (b"x" * 4096)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_download_ok_and_404(self):
        routes = {
            "/file.zip": (
                200,
                {
                    "Content-Type": "application/zip",
                    "Content-Disposition": 'attachment; filename="plugin.zip"',
                },
                PAYLOAD,
            ),
        }
        with serve(routes) as base:
            self.store.add_assets([
                {"url": f"{base}/file.zip", "kind": "archive", "priority": 0},
                {"url": f"{base}/missing.png", "kind": "image", "priority": 1},
            ])
            downloader = Downloader(
                self.store, HttpClient(delay=0, robots="ignore"), self.store.root,
                max_bytes=1024 * 1024,
            )
            result = downloader.run()
        self.assertEqual(result["downloaded"], 1)
        self.assertEqual(result["failed"], 1)
        done = self.store.assets(status="done")[0]
        path = self.store.root / done["local_path"]
        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), PAYLOAD)
        self.assertEqual(done["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertTrue(path.name.endswith("plugin.zip"))
        errors = self.store.assets(status="error")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["http_status"], 404)

    def test_robots_blocked_asset_stays_pending(self):
        routes = {
            "/robots.txt": (
                200,
                {"Content-Type": "text/plain"},
                b"User-agent: *\nDisallow: /\n",
            ),
            "/file.zip": (200, {"Content-Type": "application/zip"}, PAYLOAD),
        }
        with serve(routes) as base:
            self.store.add_assets([{"url": f"{base}/file.zip", "kind": "archive"}])
            downloader = Downloader(
                self.store, HttpClient(delay=0, robots="respect"), self.store.root,
            )
            result = downloader.run()
        self.assertEqual(result["downloaded"], 0)
        self.assertEqual(result["blocked"], 1)
        self.assertEqual(len(self.store.assets(status="pending")), 1)
        self.assertEqual(self.store.assets(status="error"), [])

    def test_max_bytes(self):
        routes = {"/big.bin": (200, {"Content-Type": "application/octet-stream"}, b"x" * 5000)}
        with serve(routes) as base:
            self.store.add_assets([{"url": f"{base}/big.bin", "kind": "archive"}])
            downloader = Downloader(
                self.store, HttpClient(delay=0, robots="ignore"), self.store.root,
                max_bytes=100,
            )
            result = downloader.run()
        self.assertEqual(result["downloaded"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(self.store.assets(status="error")[0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
