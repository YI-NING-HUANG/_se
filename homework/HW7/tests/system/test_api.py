from __future__ import annotations

import http.client
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app.py"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class DinoAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.tempdir.name) / "scores.db"
        cls.port = free_port()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        cls.proc = subprocess.Popen(
            [
                sys.executable,
                str(APP),
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
                "--db",
                str(cls.db_path),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            if cls.proc.poll() is not None:
                _, stderr = cls.proc.communicate()
                raise RuntimeError(f"server exited early: {stderr}")
            try:
                with request.urlopen(cls.url("/api/health"), timeout=0.5) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("server did not become ready")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
            cls.proc.wait(timeout=5)
        cls.tempdir.cleanup()

    @classmethod
    def url(cls, path: str) -> str:
        return f"http://127.0.0.1:{cls.port}{path}"

    def setUp(self) -> None:
        with closing(sqlite3.connect(str(self.db_path), timeout=5)) as con:
            con.execute("DELETE FROM scores")
            con.commit()

    def get(self, path: str) -> tuple[int, dict, bytes]:
        try:
            with request.urlopen(self.url(path), timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def post(self, path: str, payload: object | None = None, raw: bytes | None = None) -> tuple[int, dict, bytes]:
        body = raw if raw is not None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.url(path),
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def test_health(self) -> None:
        status, headers, body = self.get("/api/health")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["service"], "dino-run")
        self.assertIn("application/json", headers["Content-Type"])

    def test_index_page(self) -> None:
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("DINO RUN".encode("utf-8"), body)
        self.assertIn("game.js".encode("utf-8"), body)

    def test_static_assets(self) -> None:
        expected = {
            "/style.css": "text/css",
            "/game.js": "text/javascript",
            "/sw.js": "text/javascript",
            "/manifest.webmanifest": "application/manifest+json",
            "/icon.svg": "image/svg+xml",
        }
        for path, content_type in expected.items():
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertIn(content_type, headers["Content-Type"])
                self.assertGreater(len(body), 20)

    def test_service_worker_has_cache_shell(self) -> None:
        status, _, body = self.get("/sw.js")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("dino-run-v1.0.0", text)
        for asset in ["index.html", "style.css", "game.js", "icon.svg"]:
            self.assertIn(asset, text)
        self.assertIn("/api/", text)

    def test_path_traversal_is_blocked(self) -> None:
        for path in [
            "/..%2fapp.py",
            "/%2e%2e/app.py",
            "/static/../../app.py",
            "/..%5capp.py",
        ]:
            with self.subTest(path=path):
                conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
                conn.request("GET", path)
                resp = conn.getresponse()
                body = resp.read()
                conn.close()
                self.assertIn(resp.status, (400, 404))
                self.assertNotIn(b"ThreadingHTTPServer", body)

    def test_unknown_paths(self) -> None:
        status, _, _ = self.get("/api/nope")
        self.assertEqual(status, 404)
        status, _, body = self.get("/missing.html")
        self.assertEqual(status, 404)
        self.assertIn(b"404", body)

    def test_scores_start_empty(self) -> None:
        status, _, body = self.get("/api/scores")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data["scores"], [])
        self.assertEqual(data["stats"]["games"], 0)
        self.assertEqual(data["stats"]["best"], 0)

    def test_post_score_and_ranking(self) -> None:
        status, _, body = self.post("/api/scores", {"name": "Alice", "score": 123})
        data = json.loads(body)
        self.assertEqual(status, 201)
        self.assertEqual(data["rank"], 1)
        self.assertEqual(data["record"]["name"], "Alice")
        self.assertEqual(data["record"]["score"], 123)

        status, _, body = self.post("/api/scores", {"name": "Bob", "score": 500})
        data = json.loads(body)
        self.assertEqual(status, 201)
        self.assertEqual(data["rank"], 1)

        status, _, body = self.get("/api/scores?limit=10")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual([row["name"] for row in data["scores"]], ["Bob", "Alice"])
        self.assertEqual(data["stats"]["games"], 2)
        self.assertEqual(data["stats"]["best"], 500)
        self.assertEqual(data["stats"]["average"], 311.5)

    def test_tied_scores_keep_insert_order(self) -> None:
        self.post("/api/scores", {"name": "First", "score": 100})
        self.post("/api/scores", {"name": "Second", "score": 100})
        status, _, body = self.get("/api/scores")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual([row["name"] for row in data["scores"]], ["First", "Second"])

    def test_name_is_sanitized(self) -> None:
        status, _, body = self.post(
            "/api/scores", {"name": "  Ada\n  Lovelace  ", "score": 42}
        )
        data = json.loads(body)
        self.assertEqual(status, 201)
        self.assertEqual(data["record"]["name"], "Ada Lovelace")

    def test_invalid_scores_are_rejected(self) -> None:
        cases = [
            {"name": "", "score": 10},
            {"name": "   ", "score": 10},
            {"name": "x" * 17, "score": 10},
            {"name": "Alice", "score": -1},
            {"name": "Alice", "score": 1_000_001},
            {"name": "Alice", "score": "100"},
            {"name": "Alice", "score": True},
            {"name": "Alice"},
            {"score": 10},
            {"name": 12, "score": 10},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                status, _, body = self.post("/api/scores", payload)
                self.assertEqual(status, 400)
                self.assertFalse(json.loads(body)["ok"])

    def test_invalid_json_and_body(self) -> None:
        status, _, _ = self.post("/api/scores", raw=b"{")
        self.assertEqual(status, 400)
        status, _, _ = self.post("/api/scores", raw=b"[]")
        self.assertEqual(status, 400)
        status, _, _ = self.post("/api/scores", raw=b"")
        self.assertEqual(status, 400)
        status, _, _ = self.post("/api/scores", raw=b"x" * (17 * 1024))
        self.assertEqual(status, 413)

    def test_limit_is_clamped(self) -> None:
        for index in range(3):
            self.post("/api/scores", {"name": f"P{index}", "score": 10 + index})
        status, _, body = self.get("/api/scores?limit=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["scores"]), 2)
        status, _, body = self.get("/api/scores?limit=0")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["scores"]), 1)
        status, _, body = self.get("/api/scores?limit=abc")
        self.assertEqual(status, 400)

    def test_head_request(self) -> None:
        status, headers, body = self.get("/api/health")
        self.assertEqual(status, 200)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("HEAD", "/api/health")
        resp = conn.getresponse()
        payload = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(payload, b"")
        self.assertGreater(int(resp.getheader("Content-Length")), 0)

    def test_unknown_post_route(self) -> None:
        status, _, _ = self.post("/api/unknown", {"name": "Alice", "score": 1})
        self.assertEqual(status, 404)

    def test_stats_endpoint(self) -> None:
        self.post("/api/scores", {"name": "A", "score": 10})
        self.post("/api/scores", {"name": "B", "score": 30})
        status, _, body = self.get("/api/stats")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["stats"], {"games": 2, "best": 30, "average": 20.0})

    def test_cache_headers_and_nosniff(self) -> None:
        for path in ["/", "/game.js", "/style.css", "/sw.js"]:
            with self.subTest(path=path):
                _, headers, _ = self.get(path)
                self.assertEqual(headers["Cache-Control"], "no-cache")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        _, headers, _ = self.get("/icon.svg")
        self.assertIn("max-age=86400", headers["Cache-Control"])

    def test_favicon_is_served(self) -> None:
        status, headers, body = self.get("/favicon.ico")
        self.assertEqual(status, 200)
        self.assertIn("image/svg+xml", headers["Content-Type"])
        self.assertIn(b"<svg", body)

    def test_frontend_contains_required_features(self) -> None:
        code = (ROOT / "static" / "game.js").read_text(encoding="utf-8")
        for token in [
            "requestAnimationFrame",
            "spawnBird",
            "spawnCactus",
            "localStorage",
            "serviceWorker",
            "/api/scores",
            "dinoBox",
            "KeyP",
        ]:
            self.assertIn(token, code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
