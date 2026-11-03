from __future__ import annotations

import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Route:
    body: bytes = b""
    status: int = 200
    content_type: str = "text/html; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)


class MockForumServer:
    def __init__(self, routes: dict[str, Route]):
        self.routes = routes
        self.requests: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                outer.requests.append(self.path)
                route = outer.routes.get(self.path)
                if route is None:
                    body = b"<html><body>not found</body></html>"
                    self.send_response(404)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(route.status)
                self.send_header("Content-Type", route.content_type)
                for key, value in route.headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(route.body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(route.body)

            def log_message(self, format, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.port = self.httpd.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def html(body: str) -> Route:
    return Route(body.encode("utf-8"), content_type="text/html; charset=utf-8")
