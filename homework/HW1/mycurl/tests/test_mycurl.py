"""mycurl 測試 (只用標準函式庫 unittest + http.server).

執行:
  python -m unittest discover -s mycurl/tests -v
  或:
  python mycurl/tests/test_mycurl.py
"""

import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mycurl.mycurl import (  # noqa: E402
    build_parser,
    do_request,
    load_data,
    main,
    parse_header,
    resolve_output_path,
)


class EchoHandler(BaseHTTPRequestHandler):
    """測試用 server: 回傳 JSON 描述收到的請求."""

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Echo", "yes")
        self.end_headers()
        self.wfile.write(body)

    def _info(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        return {
            "method": self.command,
            "path": self.path,
            "x_token": self.headers.get("X-Token"),
            "content_type": self.headers.get("Content-Type"),
            "body": raw.decode("utf-8", "replace"),
        }

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
            return
        if self.path == "/final":
            self._send_json(200, {"ok": True, "at": "final"})
            return
        if self.path == "/notfound":
            self._send_json(404, {"error": "nope"})
            return
        self._send_json(200, self._info())

    def do_POST(self):
        self._send_json(200, self._info())

    def do_PUT(self):
        self._send_json(200, self._info())

    def log_message(self, *args):
        pass


class MyCurlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), EchoHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def base(self, path=""):
        return f"http://127.0.0.1:{self.port}{path}"

    # --- 單元測試: 小函式 ---

    def test_parse_header_ok(self):
        self.assertEqual(parse_header("X-Token: abc"), ("X-Token", "abc"))
        self.assertEqual(parse_header("A:b:c"), ("A", "b:c"))

    def test_parse_header_bad(self):
        with self.assertRaises(ValueError):
            parse_header("no-colon")

    def test_load_data_join(self):
        body, is_json = load_data(["a=1", "b=2"], None)
        self.assertEqual(body, b"a=1&b=2")
        self.assertFalse(is_json)

    def test_load_data_json(self):
        body, is_json = load_data([], '{"a":1}')
        self.assertEqual(body, b'{"a":1}')
        self.assertTrue(is_json)

    def test_resolve_output_path(self):
        self.assertEqual(resolve_output_path("x.html", False, "http://h/a"), "x.html")
        self.assertEqual(
            resolve_output_path(None, True, "http://h/dir/file.txt"), "file.txt")

    # --- 整合測試: 真實 HTTP ---

    def test_get(self):
        status, headers, data, url = do_request(
            self.base("/hello"), "GET", [], None, 5, None, False, 5, False)
        self.assertEqual(status, 200)
        obj = json.loads(data)
        self.assertEqual(obj["method"], "GET")
        self.assertEqual(obj["path"], "/hello")

    def test_post_with_header_and_data(self):
        status, headers, data, url = do_request(
            self.base("/submit"), "POST", [("X-Token", "abc")],
            b"a=1&b=2", 5, None, False, 5, False)
        self.assertEqual(status, 200)
        obj = json.loads(data)
        self.assertEqual(obj["x_token"], "abc")
        self.assertEqual(obj["body"], "a=1&b=2")

    def test_redirect_follow(self):
        status, _, data, url = do_request(
            self.base("/redirect"), "GET", [], None, 5, None, True, 5, False)
        self.assertEqual(status, 200)
        self.assertTrue(url.endswith("/final"))

    def test_redirect_no_follow(self):
        status, _, _, _ = do_request(
            self.base("/redirect"), "GET", [], None, 5, None, False, 5, False)
        self.assertEqual(status, 302)

    def test_404_status(self):
        status, _, data, _ = do_request(
            self.base("/notfound"), "GET", [], None, 5, None, False, 5, False)
        self.assertEqual(status, 404)

    def test_cli_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out.json")
            rc = main([self.base("/hi"), "-o", out, "-s"])
            self.assertEqual(rc, 0)
            with open(out, "rb") as f:
                obj = json.loads(f.read())
            self.assertEqual(obj["path"], "/hi")

    def test_cli_fail_flag(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.txt")
            rc = main([self.base("/notfound"), "-o", out, "--fail", "-s"])
            self.assertEqual(rc, 22)
            self.assertFalse(os.path.exists(out))

    def test_cli_bad_header(self):
        rc = main([self.base("/"), "-H", "badheader", "-s"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
