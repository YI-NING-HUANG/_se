from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Iterator

from .util import ensure_dir, utc_now

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS forums (
    forum_id TEXT PRIMARY KEY,
    parent_id TEXT,
    title TEXT,
    url TEXT,
    description TEXT,
    captured_threads INTEGER DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    forum_id TEXT,
    title TEXT,
    author TEXT,
    url TEXT,
    reply_count INTEGER DEFAULT 0,
    post_count INTEGER DEFAULT 0,
    created_at TEXT,
    last_post_at TEXT,
    page_count INTEGER DEFAULT 0,
    pages_fetched INTEGER DEFAULT 0,
    status TEXT,
    source TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    post_index INTEGER,
    author TEXT,
    author_url TEXT,
    posted_at TEXT,
    content_html TEXT,
    content_text TEXT,
    url TEXT,
    edited_at TEXT,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_thread ON posts(thread_id, post_index);

CREATE TABLE IF NOT EXISTS assets (
    url TEXT PRIMARY KEY,
    source_url TEXT,
    kind TEXT,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'pending',
    http_status INTEGER,
    content_type TEXT,
    size INTEGER,
    sha256 TEXT,
    blob_path TEXT,
    local_path TEXT,
    filename TEXT,
    thread_id TEXT,
    post_id TEXT,
    referer TEXT,
    error TEXT,
    attempts INTEGER DEFAULT 0,
    fetched_at TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status, priority);
CREATE INDEX IF NOT EXISTS idx_assets_thread ON assets(thread_id);

CREATE TABLE IF NOT EXISTS links (
    src_url TEXT,
    target_url TEXT,
    kind TEXT,
    text TEXT,
    PRIMARY KEY (src_url, target_url, kind)
);

CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);
"""


class Store:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        ensure_dir(self.root)
        ensure_dir(self.root / "blobs")
        ensure_dir(self.root / "raw")
        ensure_dir(self.root / "site")
        self.db_path = self.root / "xfrescue.sqlite3"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ meta
    def set_meta(self, key: str, value) -> None:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        with self.conn:
            self.conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_meta(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    # ---------------------------------------------------------------- forums
    def upsert_forums(self, forums: Iterable[dict]) -> None:
        rows = []
        now = utc_now()
        for f in forums:
            rows.append(
                (
                    str(f.get("forumId") or f.get("forum_id") or ""),
                    f.get("parentForumId") or f.get("parent_id"),
                    f.get("title"),
                    f.get("originalUrl") or f.get("url"),
                    f.get("description"),
                    f.get("capturedThreadCount") or f.get("captured_threads") or 0,
                    now,
                )
            )
        with self.conn:
            self.conn.executemany(
                """INSERT INTO forums(forum_id, parent_id, title, url, description,
                                      captured_threads, updated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(forum_id) DO UPDATE SET
                     parent_id=excluded.parent_id,
                     title=excluded.title,
                     url=excluded.url,
                     description=excluded.description,
                     captured_threads=excluded.captured_threads,
                     updated_at=excluded.updated_at""",
                rows,
            )

    def forums(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM forums ORDER BY title"))

    # --------------------------------------------------------------- threads
    def upsert_threads(self, threads: Iterable[dict], forum_id: str | None = None,
                       source: str = "archive") -> None:
        rows = []
        now = utc_now()
        for t in threads:
            tid = str(t.get("threadId") or t.get("thread_id") or "")
            if not tid:
                continue
            rows.append(
                (
                    tid,
                    str(t.get("forumId") or forum_id or ""),
                    t.get("title"),
                    t.get("authorName") or t.get("author"),
                    t.get("originalUrl") or t.get("url"),
                    int(t.get("replyCount") or t.get("reply_count") or 0),
                    int(t.get("postCount") or t.get("post_count") or 0),
                    t.get("createdAt") or t.get("created_at"),
                    t.get("lastPostAt") or t.get("last_post_at"),
                    int(t.get("pageCount") or t.get("page_count") or 0),
                    0,
                    t.get("status"),
                    source,
                    now,
                )
            )
        with self.conn:
            self.conn.executemany(
                """INSERT INTO threads(thread_id, forum_id, title, author, url,
                                       reply_count, post_count, created_at, last_post_at,
                                       page_count, pages_fetched, status, source, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(thread_id) DO UPDATE SET
                     forum_id=COALESCE(excluded.forum_id, threads.forum_id),
                     title=COALESCE(excluded.title, threads.title),
                     author=COALESCE(excluded.author, threads.author),
                     url=COALESCE(excluded.url, threads.url),
                     reply_count=MAX(threads.reply_count, excluded.reply_count),
                     post_count=MAX(threads.post_count, excluded.post_count),
                     created_at=COALESCE(excluded.created_at, threads.created_at),
                     last_post_at=COALESCE(excluded.last_post_at, threads.last_post_at),
                     page_count=MAX(threads.page_count, excluded.page_count),
                     status=COALESCE(excluded.status, threads.status),
                     updated_at=excluded.updated_at""",
                rows,
            )

    def set_thread_pages(self, thread_id: str, pages_fetched: int,
                         page_count: int | None = None) -> None:
        with self.conn:
            if page_count is None:
                self.conn.execute(
                    "UPDATE threads SET pages_fetched=?, updated_at=? WHERE thread_id=?",
                    (pages_fetched, utc_now(), str(thread_id)),
                )
            else:
                self.conn.execute(
                    "UPDATE threads SET pages_fetched=?, page_count=?, updated_at=? WHERE thread_id=?",
                    (pages_fetched, page_count, utc_now(), str(thread_id)),
                )

    def thread(self, thread_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM threads WHERE thread_id=?", (str(thread_id),)
        ).fetchone()

    def iter_threads(self, forum_id: str | None = None,
                     incomplete_only: bool = False) -> Iterator[sqlite3.Row]:
        sql = "SELECT * FROM threads"
        args: list = []
        where = []
        if forum_id is not None:
            where.append("forum_id=?")
            args.append(str(forum_id))
        if incomplete_only:
            where.append("pages_fetched < page_count")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY thread_id"
        yield from self.conn.execute(sql, args)

    # ----------------------------------------------------------------- posts
    def upsert_posts(self, posts: Iterable[dict], source: str = "archive") -> int:
        rows = []
        for p in posts:
            pid = str(p.get("postId") or p.get("post_id") or "")
            tid = str(p.get("threadId") or p.get("thread_id") or "")
            if not pid or not tid:
                continue
            rows.append(
                (
                    pid,
                    tid,
                    int(p.get("postIndex") or p.get("post_index") or 0),
                    p.get("authorName") or p.get("author"),
                    p.get("authorProfileUrl") or p.get("author_url"),
                    p.get("postedAt") or p.get("posted_at"),
                    p.get("contentHtml") or p.get("content_html"),
                    p.get("contentText") or p.get("content_text"),
                    p.get("originalUrl") or p.get("url"),
                    p.get("editedAt") or p.get("edited_at"),
                    source,
                )
            )
        with self.conn:
            self.conn.executemany(
                """INSERT INTO posts(post_id, thread_id, post_index, author, author_url,
                                     posted_at, content_html, content_text, url, edited_at, source)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(post_id) DO UPDATE SET
                     thread_id=excluded.thread_id,
                     post_index=excluded.post_index,
                     author=COALESCE(excluded.author, posts.author),
                     author_url=COALESCE(excluded.author_url, posts.author_url),
                     posted_at=COALESCE(excluded.posted_at, posts.posted_at),
                     content_html=COALESCE(excluded.content_html, posts.content_html),
                     content_text=COALESCE(excluded.content_text, posts.content_text),
                     url=COALESCE(excluded.url, posts.url),
                     edited_at=COALESCE(excluded.edited_at, posts.edited_at),
                     source=excluded.source""",
                rows,
            )
        return len(rows)

    def iter_posts(self, thread_id: str) -> Iterator[sqlite3.Row]:
        yield from self.conn.execute(
            "SELECT * FROM posts WHERE thread_id=? ORDER BY post_index, post_id",
            (str(thread_id),),
        )

    def post(self, post_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM posts WHERE post_id=?", (str(post_id),)
        ).fetchone()

    # ----------------------------------------------------------------- links
    def add_links(self, links: Iterable[tuple[str, str, str, str]]) -> None:
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO links(src_url, target_url, kind, text) VALUES(?,?,?,?)",
                list(links),
            )

    # ---------------------------------------------------------------- assets
    def add_assets(self, assets: Iterable[dict]) -> int:
        rows = []
        now = utc_now()
        for a in assets:
            url = a.get("url")
            if not url:
                continue
            priority = a.get("priority")
            rows.append(
                (
                    url,
                    a.get("source_url") or url,
                    a.get("kind") or "external_link",
                    int(priority) if priority is not None else 5,
                    a.get("status") or "pending",
                    a.get("thread_id"),
                    a.get("post_id"),
                    a.get("referer"),
                    now,
                )
            )
        with self.conn:
            before = self.conn.total_changes
            self.conn.executemany(
                """INSERT OR IGNORE INTO assets(url, source_url, kind, priority, status,
                                                thread_id, post_id, referer, created_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            return self.conn.total_changes - before

    def pending_assets(self, kinds: Iterable[str] | None = None,
                       limit: int | None = None,
                       include_link_only: bool = False) -> list[sqlite3.Row]:
        sql = "SELECT * FROM assets WHERE status IN ('pending','link_only')"
        args: list = []
        if not include_link_only:
            sql = "SELECT * FROM assets WHERE status='pending'"
        if kinds:
            kinds = list(kinds)
            sql += " AND kind IN (" + ",".join("?" for _ in kinds) + ")"
            args.extend(kinds)
        sql += " ORDER BY priority, url"
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        return list(self.conn.execute(sql, args))

    def mark_asset(self, url: str, **fields) -> None:
        allowed = {
            "status", "http_status", "content_type", "size", "sha256", "blob_path",
            "local_path", "filename", "error", "fetched_at",
        }
        sets = []
        args = []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"unknown asset field: {key}")
            sets.append(f"{key}=?")
            args.append(value)
        if not sets:
            return
        sets.append("attempts=attempts+1")
        args.append(url)
        with self.conn:
            self.conn.execute(f"UPDATE assets SET {', '.join(sets)} WHERE url=?", args)

    def reset_asset_errors(self) -> int:
        with self.conn:
            cur = self.conn.execute(
                "UPDATE assets SET status='pending', error=NULL WHERE status='error'"
            )
            return cur.rowcount

    def assets(self, status: str | None = None, kind: str | None = None,
               thread_id: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM assets"
        where = []
        args = []
        if status:
            where.append("status=?")
            args.append(status)
        if kind:
            where.append("kind=?")
            args.append(kind)
        if thread_id:
            where.append("thread_id=?")
            args.append(str(thread_id))
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY priority, url"
        return list(self.conn.execute(sql, args))

    def asset_map(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT url, local_path FROM assets WHERE local_path IS NOT NULL"
        )
        return {row["url"]: row["local_path"] for row in rows}

    # --------------------------------------------------------------- reports
    def counts(self) -> dict:
        def one(sql: str, *args):
            row = self.conn.execute(sql, args).fetchone()
            return row[0] if row else 0

        return {
            "forums": one("SELECT COUNT(*) FROM forums"),
            "threads": one("SELECT COUNT(*) FROM threads"),
            "threads_complete": one(
                "SELECT COUNT(*) FROM threads WHERE page_count>0 AND pages_fetched>=page_count"
            ),
            "posts": one("SELECT COUNT(*) FROM posts"),
            "assets": one("SELECT COUNT(*) FROM assets"),
            "assets_done": one("SELECT COUNT(*) FROM assets WHERE status='done'"),
            "assets_pending": one("SELECT COUNT(*) FROM assets WHERE status='pending'"),
            "assets_error": one("SELECT COUNT(*) FROM assets WHERE status='error'"),
            "assets_skipped": one("SELECT COUNT(*) FROM assets WHERE status='skipped'"),
            "assets_link_only": one("SELECT COUNT(*) FROM assets WHERE status='link_only'"),
            "asset_bytes": one("SELECT COALESCE(SUM(size),0) FROM assets WHERE status='done'"),
            "links": one("SELECT COUNT(*) FROM links"),
        }

    def export_jsonl(self, path: str | Path, what: str) -> int:
        path = Path(path)
        ensure_dir(path.parent)
        count = 0
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            if what == "threads":
                rows = self.conn.execute("SELECT * FROM threads ORDER BY thread_id")
            elif what == "posts":
                rows = self.conn.execute("SELECT * FROM posts ORDER BY thread_id, post_index")
            elif what == "assets":
                rows = self.conn.execute("SELECT * FROM assets ORDER BY priority, url")
            elif what == "forums":
                rows = self.conn.execute("SELECT * FROM forums ORDER BY forum_id")
            else:
                raise ValueError(f"unknown export: {what}")
            for row in rows:
                fh.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
                count += 1
        return count

    def export_assets_csv(self, path: str | Path) -> int:
        path = Path(path)
        ensure_dir(path.parent)
        rows = self.assets()
        fields = [
            "url", "kind", "status", "http_status", "content_type", "size", "sha256",
            "local_path", "filename", "thread_id", "post_id", "error", "fetched_at",
        ]
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        return len(rows)
