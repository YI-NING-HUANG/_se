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

CREATE TABLE IF NOT EXISTS seeds (
    url TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue (
    url TEXT PRIMARY KEY,
    depth INTEGER NOT NULL DEFAULT 0,
    parent_url TEXT,
    priority INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    added_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_queue_pick ON queue(status, priority, depth, added_at);

CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    final_url TEXT,
    parent_url TEXT,
    depth INTEGER NOT NULL DEFAULT 0,
    kind TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'done',
    http_status INTEGER,
    content_type TEXT,
    encoding TEXT,
    size INTEGER,
    sha256 TEXT,
    raw_path TEXT,
    text TEXT,
    base_url TEXT,
    next_url TEXT,
    fetched_at TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pages_kind ON pages(kind);
CREATE INDEX IF NOT EXISTS idx_pages_final ON pages(final_url);

CREATE TABLE IF NOT EXISTS aliases (
    url TEXT PRIMARY KEY,
    page_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    url TEXT PRIMARY KEY,
    final_url TEXT,
    page_url TEXT,
    kind TEXT,
    priority INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'pending',
    http_status INTEGER,
    content_type TEXT,
    size INTEGER,
    sha256 TEXT,
    filename TEXT,
    local_path TEXT,
    referer TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_pick ON assets(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_assets_page ON assets(page_url);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);

CREATE TABLE IF NOT EXISTS links (
    src_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    rel TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    internal INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (src_url, target_url, rel, text)
);

CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);
"""


class Store:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        ensure_dir(self.root)
        ensure_dir(self.root / "raw" / "pages")
        ensure_dir(self.root / "blobs")
        ensure_dir(self.root / "site")
        self.db_path = self.root / "forumkeep.sqlite3"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute(
            "UPDATE queue SET status='pending' WHERE status='working'"
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

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

    def get_json_meta(self, key: str, default=None):
        value = self.get_meta(key)
        if value is None:
            return default
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default

    def add_seed(self, url: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO seeds(url, added_at) VALUES(?, ?)",
                (url, utc_now()),
            )

    def seeds(self) -> list[str]:
        return [
            row["url"]
            for row in self.conn.execute("SELECT url FROM seeds ORDER BY added_at")
        ]

    def enqueue_page(
        self,
        url: str,
        depth: int = 0,
        parent_url: str | None = None,
        priority: int = 5,
    ) -> bool:
        now = utc_now()
        existing = self.conn.execute(
            "SELECT status, depth, priority FROM queue WHERE url=?", (url,)
        ).fetchone()
        if existing:
            if existing["status"] == "done":
                return False
            if existing["status"] == "error":
                return False
            with self.conn:
                self.conn.execute(
                    """UPDATE queue SET depth=?, parent_url=COALESCE(parent_url, ?),
                       priority=?, updated_at=? WHERE url=?""",
                    (min(depth, existing["depth"]), parent_url,
                     min(priority, existing["priority"]), now, url),
                )
            return False
        if self.get_page(url):
            return False
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO queue(
                       url, depth, parent_url, priority, status, added_at
                   ) VALUES(?, ?, ?, ?, 'pending', ?)""",
                (url, depth, parent_url, priority, now),
            )
        return True

    def next_queued_page(self) -> sqlite3.Row | None:
        return self.conn.execute(
            """SELECT * FROM queue WHERE status='pending'
               ORDER BY priority ASC, depth ASC, added_at ASC LIMIT 1"""
        ).fetchone()

    def mark_queue_working(self, url: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE queue SET status='working', attempts=attempts+1, updated_at=? WHERE url=?",
                (utc_now(), url),
            )

    def mark_queue(
        self, url: str, status: str, error: str | None = None
    ) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE queue SET status=?, error=?, updated_at=? WHERE url=?",
                (status, error, utc_now(), url),
            )

    def requeue_all_pages(self) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE queue SET status='pending', error=NULL, updated_at=? "
                "WHERE status='done'",
                (utc_now(),),
            )
            return cursor.rowcount

    def reset_errors(self) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE queue SET status='pending', error=NULL, updated_at=? "
                "WHERE status IN ('error', 'blocked')",
                (utc_now(),),
            )
            return cursor.rowcount

    def queue_counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM queue GROUP BY status"
        ).fetchall()
        return {row["status"]: row["n"] for row in rows}

    def get_page(self, url: str) -> sqlite3.Row | None:
        row = self.conn.execute("SELECT * FROM pages WHERE url=?", (url,)).fetchone()
        if row:
            return row
        alias = self.conn.execute(
            "SELECT page_url FROM aliases WHERE url=?", (url,)
        ).fetchone()
        if alias:
            return self.conn.execute(
                "SELECT * FROM pages WHERE url=?", (alias["page_url"],)
            ).fetchone()
        return None

    def find_page_by_final(self, final_url: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM pages WHERE final_url=? OR url=? LIMIT 1",
            (final_url, final_url),
        ).fetchone()

    def upsert_page(self, page: dict) -> None:
        now = utc_now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO pages(
                       url, final_url, parent_url, depth, kind, title, status,
                       http_status, content_type, encoding, size, sha256,
                       raw_path, text, base_url, next_url, fetched_at, error, attempts
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(url) DO UPDATE SET
                       final_url=excluded.final_url,
                       parent_url=COALESCE(excluded.parent_url, pages.parent_url),
                       depth=MIN(pages.depth, excluded.depth),
                       kind=COALESCE(excluded.kind, pages.kind),
                       title=COALESCE(excluded.title, pages.title),
                       status=excluded.status,
                       http_status=excluded.http_status,
                       content_type=excluded.content_type,
                       encoding=excluded.encoding,
                       size=excluded.size,
                       sha256=excluded.sha256,
                       raw_path=excluded.raw_path,
                       text=COALESCE(excluded.text, pages.text),
                       base_url=excluded.base_url,
                       next_url=excluded.next_url,
                       fetched_at=excluded.fetched_at,
                       error=excluded.error,
                       attempts=excluded.attempts""",
                (
                    page["url"],
                    page.get("final_url") or page["url"],
                    page.get("parent_url"),
                    int(page.get("depth") or 0),
                    page.get("kind"),
                    page.get("title"),
                    page.get("status") or "done",
                    page.get("http_status"),
                    page.get("content_type"),
                    page.get("encoding"),
                    page.get("size"),
                    page.get("sha256"),
                    page.get("raw_path"),
                    page.get("text"),
                    page.get("base_url"),
                    page.get("next_url"),
                    page.get("fetched_at") or now,
                    page.get("error"),
                    int(page.get("attempts") or 0),
                ),
            )

    def add_alias(self, url: str, page_url: str) -> None:
        if url == page_url:
            return
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO aliases(url, page_url) VALUES(?, ?)",
                (url, page_url),
            )

    def alias_map(self) -> dict[str, str]:
        return {
            row["url"]: row["page_url"]
            for row in self.conn.execute("SELECT url, page_url FROM aliases")
        }

    def mark_page_bad(self, url: str, error: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE pages SET status='error', error=? WHERE url=?",
                (error[:1000], url),
            )
            row = self.conn.execute(
                "SELECT url FROM queue WHERE url=?", (url,)
            ).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE queue SET status='pending', error=? WHERE url=?",
                    (error[:1000], url),
                )
            else:
                self.conn.execute(
                    """INSERT INTO queue(url, depth, parent_url, priority, status,
                                         error, added_at)
                       VALUES(?, 0, NULL, 5, 'pending', ?, ?)""",
                    (url, error[:1000], utc_now()),
                )

    def mark_asset_pending(self, url: str, error: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE assets SET status='pending', error=? WHERE url=?",
                (error, url),
            )

    def pages(self, kind: str | None = None) -> list[sqlite3.Row]:
        if kind:
            return list(self.conn.execute(
                "SELECT * FROM pages WHERE status='done' AND kind=? ORDER BY depth, title",
                (kind,),
            ))
        return list(self.conn.execute(
            "SELECT * FROM pages WHERE status='done' ORDER BY depth, title"
        ))

    def iter_pages(self) -> Iterator[sqlite3.Row]:
        yield from self.conn.execute("SELECT * FROM pages ORDER BY depth, url")

    def add_link(
        self, src_url: str, target_url: str, rel: str = "",
        text: str = "", internal: bool = False
    ) -> None:
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO links(src_url, target_url, rel, text, internal)
                   VALUES(?,?,?,?,?)""",
                (src_url, target_url, rel, text[:500], 1 if internal else 0),
            )

    def enqueue_asset(
        self,
        url: str,
        page_url: str | None = None,
        kind: str = "other",
        priority: int = 5,
        referer: str | None = None,
    ) -> bool:
        now = utc_now()
        existing = self.conn.execute(
            "SELECT status FROM assets WHERE url=?", (url,)
        ).fetchone()
        if existing:
            return False
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO assets(
                       url, page_url, kind, priority, status, referer, created_at
                   ) VALUES(?, ?, ?, ?, 'pending', ?, ?)""",
                (url, page_url, kind, priority, referer or page_url, now),
            )
        return True

    def pending_assets(
        self,
        kinds: set[str] | None = None,
        host: str | None = None,
        limit: int | None = None,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM assets WHERE status='pending'"
        params: list = []
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            sql += f" AND kind IN ({placeholders})"
            params.extend(sorted(kinds))
        if host:
            sql += " AND url LIKE ?"
            params.append(f"%://{host}/%")
        sql += " ORDER BY priority ASC, created_at ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return list(self.conn.execute(sql, params))

    def get_asset(self, url: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM assets WHERE url=?", (url,)).fetchone()

    def mark_asset_done(
        self,
        url: str,
        *,
        final_url: str,
        http_status: int,
        content_type: str,
        size: int,
        sha256: str,
        filename: str,
        local_path: str,
        kind: str | None = None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """UPDATE assets SET final_url=?, status='done', http_status=?,
                   content_type=?, size=?, sha256=?, filename=?, local_path=?,
                   kind=COALESCE(?, kind), fetched_at=?, error=NULL,
                   attempts=attempts+1 WHERE url=?""",
                (final_url, http_status, content_type, size, sha256, filename,
                 local_path, kind, utc_now(), url),
            )

    def mark_asset_error(
        self, url: str, error: str, status: str = "error",
        http_status: int | None = None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """UPDATE assets SET status=?, error=?, http_status=COALESCE(?, http_status),
                   attempts=attempts+1, fetched_at=? WHERE url=?""",
                (status, error[:1000], http_status, utc_now(), url),
            )

    def reset_asset_errors(self) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE assets SET status='pending', error=NULL "
                "WHERE status IN ('error', 'blocked')"
            )
            return cursor.rowcount

    def assets(self, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return list(self.conn.execute(
                "SELECT * FROM assets WHERE status=? ORDER BY priority, url", (status,)
            ))
        return list(self.conn.execute(
            "SELECT * FROM assets ORDER BY priority, url"
        ))

    def iter_assets(self, status: str | None = None) -> Iterator[sqlite3.Row]:
        if status:
            yield from self.conn.execute(
                "SELECT * FROM assets WHERE status=? ORDER BY priority, url", (status,)
            )
        else:
            yield from self.conn.execute("SELECT * FROM assets ORDER BY priority, url")

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for table in ("pages", "assets", "links", "aliases"):
            result[table] = self.conn.execute(
                f"SELECT COUNT(*) AS n FROM {table}"
            ).fetchone()["n"]
        result.update({f"queue_{k}": v for k, v in self.queue_counts().items()})
        result["asset_bytes"] = self.conn.execute(
            "SELECT COALESCE(SUM(size), 0) AS n FROM assets WHERE status='done'"
        ).fetchone()["n"]
        result["page_bytes"] = self.conn.execute(
            "SELECT COALESCE(SUM(size), 0) AS n FROM pages WHERE status='done'"
        ).fetchone()["n"]
        return result

    def errors(self, limit: int = 20) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """SELECT 'page' AS type, url, status, error FROM pages
               WHERE error IS NOT NULL
               UNION ALL
               SELECT 'queue' AS type, url, status, error FROM queue
               WHERE error IS NOT NULL AND status IN ('error', 'blocked')
               UNION ALL
               SELECT 'asset' AS type, url, status, error FROM assets
               WHERE error IS NOT NULL
               ORDER BY type LIMIT ?""",
            (limit,),
        ).fetchall()
        return list(rows)

    def export_jsonl(self, path: str | Path, what: str = "all") -> int:
        path = Path(path)
        ensure_dir(path.parent)
        counts = 0
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            for table, key in (("pages", "pages"), ("assets", "assets"), ("links", "links")):
                if what not in {key, "all"}:
                    continue
                for row in self.conn.execute(f"SELECT * FROM {table}"):
                    handle.write(json.dumps({"type": key[:-1], **dict(row)},
                                            ensure_ascii=False) + "\n")
                    counts += 1
        return counts

    def export_csv(self, directory: str | Path, what: str = "all") -> int:
        directory = Path(directory)
        ensure_dir(directory)
        counts = 0
        for table in ("pages", "assets", "links"):
            if what not in {table, "all"}:
                continue
            rows = self.conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                continue
            target = directory / f"{table}.csv"
            with open(target, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(rows[0].keys())
                writer.writerows([tuple(row) for row in rows])
                counts += len(rows)
        return counts
