#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB = BASE_DIR / "data" / "scores.db"
MAX_BODY = 16 * 1024
MAX_SCORE = 1_000_000
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


class Leaderboard:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_scores_rank ON scores (score DESC, id ASC)"
            )
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def add(self, name: str, score: int) -> tuple[dict, int]:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(self._connect()) as con:
            cur = con.execute(
                "INSERT INTO scores (name, score, created_at) VALUES (?, ?, ?)",
                (name, score, created_at),
            )
            con.commit()
            row_id = int(cur.lastrowid)
            rank = con.execute(
                """
                SELECT COUNT(*) + 1 FROM scores
                WHERE score > ? OR (score = ? AND id < ?)
                """,
                (score, score, row_id),
            ).fetchone()[0]
        record = {
            "id": row_id,
            "name": name,
            "score": score,
            "created_at": created_at,
        }
        return record, int(rank)

    def top(self, limit: int) -> list[dict]:
        with closing(self._connect()) as con:
            rows = con.execute(
                """
                SELECT id, name, score, created_at FROM scores
                ORDER BY score DESC, id ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict:
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT COUNT(*) AS games, COALESCE(MAX(score), 0) AS best, "
                "COALESCE(AVG(score), 0) AS average FROM scores"
            ).fetchone()
        return {
            "games": int(row["games"]),
            "best": int(row["best"]),
            "average": round(float(row["average"]), 1),
        }


def clean_name(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    name = CONTROL_CHARS.sub(" ", raw)
    name = re.sub(r"\s+", " ", name).strip()
    if not 1 <= len(name) <= 16:
        return None
    return name


def valid_score(raw: object) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    if not 0 <= raw <= MAX_SCORE:
        return None
    return raw


class DinoHandler(BaseHTTPRequestHandler):
    server_version = "DinoRun/1.0"
    protocol_version = "HTTP/1.1"
    static_dir = STATIC_DIR
    leaderboard: Leaderboard

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        path = parts.path
        if path == "/api/health":
            self.send_json(
                HTTPStatus.OK,
                {"ok": True, "service": "dino-run", "version": "1.0"},
            )
        elif path == "/api/scores":
            try:
                limit = int(parse_qs(parts.query).get("limit", ["10"])[0])
            except ValueError:
                return self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "limit 必須是整數"},
                )
            limit = max(1, min(limit, 50))
            self.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "scores": self.leaderboard.top(limit),
                    "stats": self.leaderboard.stats(),
                },
            )
        elif path == "/api/stats":
            self.send_json(
                HTTPStatus.OK,
                {"ok": True, "stats": self.leaderboard.stats()},
            )
        elif path == "/favicon.ico":
            self.serve_static("/icon.svg")
        elif path.startswith("/api/"):
            self.send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "找不到這個 API"},
            )
        else:
            self.serve_static(path)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != "/api/scores":
            return self.send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "找不到這個 API"},
            )
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "Content-Length 格式錯誤"},
            )
        if length <= 0:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "缺少請求內容"},
            )
        if length > MAX_BODY:
            self.close_connection = True
            return self.send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"ok": False, "error": "請求內容過大"},
            )
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "JSON 格式錯誤"},
            )
        if not isinstance(payload, dict):
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "JSON 必須是物件"},
            )
        name = clean_name(payload.get("name"))
        if name is None:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "名字長度需為 1 到 16 個字"},
            )
        score = valid_score(payload.get("score"))
        if score is None:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "分數需為 0 到 1000000 的整數"},
            )
        record, rank = self.leaderboard.add(name, score)
        self.send_json(
            HTTPStatus.CREATED,
            {"ok": True, "record": record, "rank": rank},
        )

    def _write(self, data: bytes) -> None:
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            self.close_connection = True

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self._write(body)

    def serve_static(self, url_path: str) -> None:
        try:
            relative = unquote(url_path).lstrip("/")
        except UnicodeDecodeError:
            return self.send_static_error(HTTPStatus.BAD_REQUEST)
        if not relative or relative.endswith("/"):
            relative += "index.html"
        if "\x00" in relative:
            return self.send_static_error(HTTPStatus.BAD_REQUEST)
        root = self.static_dir.resolve()
        try:
            target = (root / relative).resolve()
            target.relative_to(root)
        except (ValueError, OSError):
            return self.send_static_error(HTTPStatus.NOT_FOUND)
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            return self.send_static_error(HTTPStatus.NOT_FOUND)
        try:
            data = target.read_bytes()
        except OSError:
            return self.send_static_error(HTTPStatus.INTERNAL_SERVER_ERROR)
        content_type = CONTENT_TYPES.get(target.suffix.lower())
        if content_type is None:
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix.lower() in {".html", ".css", ".js", ".webmanifest"}:
            cache = "no-cache"
        else:
            cache = "public, max-age=86400"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self._write(data)

    def send_static_error(self, status: int) -> None:
        if status == HTTPStatus.NOT_FOUND:
            message = (
                "<!doctype html><meta charset=utf-8><title>404</title>"
                "<h1>404 Not Found</h1><p><a href=/>回到 DINO RUN</a></p>"
            ).encode("utf-8")
        else:
            message = "<!doctype html><meta charset=utf-8><h1>Error</h1>".encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(message)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self._write(message)


def build_server(host: str, port: int, db_path: Path) -> ThreadingHTTPServer:
    leaderboard = Leaderboard(db_path)
    handler = type(
        "BoundDinoHandler",
        (DinoHandler,),
        {"leaderboard": leaderboard, "static_dir": STATIC_DIR},
    )
    return ThreadingHTTPServer((host, port), handler)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DINO RUN：離線可玩的小恐龍遊戲 + SQLite 排行榜"
    )
    parser.add_argument("--host", default="127.0.0.1", help="監聽位址")
    parser.add_argument("--port", type=int, default=8787, help="監聽埠")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 檔案路徑")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    server = build_server(args.host, args.port, args.db)
    host, port = server.server_address[:2]
    print("DINO RUN 已啟動：http://%s:%s/" % (host, port))
    print("資料庫：%s" % args.db.resolve())
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
