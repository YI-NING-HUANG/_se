from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

from .db import Store
from .extract import extract_assets
from .net import FetchError, HttpClient
from .util import ensure_dir, write_json

ARCHIVE_BASE = "https://rpgmakerchat.com"


def parse_thread_id(value: str) -> str:
    value = (value or "").strip()
    if re.fullmatch(r"\d+", value):
        return value
    match = re.search(r"/threads/[^/?#]+?\.(\d+)(?:/|$)", value)
    if match:
        return match.group(1)
    match = re.search(r"[?&]thread(?:id)?=(\d+)", value)
    if match:
        return match.group(1)
    match = re.search(r"/thread/(\d+)", value)
    if match:
        return match.group(1)
    raise ValueError(f"cannot parse thread id from: {value}")


def parse_forum_id(value: str) -> str:
    value = (value or "").strip()
    if re.fullmatch(r"\d+", value):
        return value
    match = re.search(r"/forums/[^/?#]+?\.(\d+)(?:/|$)", value)
    if match:
        return match.group(1)
    match = re.search(r"[?&]forum(?:id)?=(\d+)", value)
    if match:
        return match.group(1)
    match = re.search(r"/forum/(\d+)", value)
    if match:
        return match.group(1)
    raise ValueError(f"cannot parse forum id from: {value}")


class ArchiveAPI:
    """Client for the public rpgmakerchat.com archive API.

    The API is an independent community archive of the old RPG Maker Web forum.
    It exposes forum/thread/post JSON and is explicitly allowed by robots.txt.
    """

    def __init__(self, client: HttpClient, base: str = ARCHIVE_BASE, root: str | Path | None = None,
                 save_raw: bool = True):
        self.client = client
        self.base = base.rstrip("/")
        self.root = Path(root) if root else None
        self.save_raw = save_raw

    def forums(self) -> list[dict]:
        data = self.client.get_json(f"{self.base}/api/forums")
        return data.get("forums") or []

    def forum_threads(self, forum_id: str, page: int = 1) -> dict:
        url = f"{self.base}/api/forum/{urllib.parse.quote(str(forum_id))}/threads?page={page}"
        return self.client.get_json(url)

    def thread(self, thread_id: str, page: int = 1) -> dict:
        url = f"{self.base}/api/thread/{urllib.parse.quote(str(thread_id))}?page={page}"
        return self.client.get_json(url)

    def discover_thread(self, store: Store, thread_id: str, max_pages: int | None = None,
                        save_raw: bool | None = None) -> dict:
        thread_id = parse_thread_id(str(thread_id))
        save_raw = self.save_raw if save_raw is None else save_raw
        first = self.thread(thread_id, 1)
        thread = first.get("thread") or {}
        if not thread:
            raise FetchError(f"thread {thread_id} not found", status=404)
        if thread.get("forumId"):
            store.upsert_forums(
                [{
                    "forumId": thread.get("forumId"),
                    "title": thread.get("forumTitle"),
                    "originalUrl": thread.get("forumOriginalUrl"),
                }]
            )
        page_count = int(first.get("pageCount") or thread.get("pageCount") or 1)
        if max_pages:
            page_count = min(page_count, max_pages)
        store.upsert_threads([thread], source="archive")
        total_posts = 0
        for page in range(1, page_count + 1):
            data = first if page == 1 else self.thread(thread_id, page)
            posts = data.get("posts") or []
            for post in posts:
                post.setdefault("threadId", thread_id)
            total_posts += store.upsert_posts(posts, source="archive")
            self._index_posts(store, thread_id, thread, posts)
            store.set_thread_pages(thread_id, page, page_count)
            if save_raw and self.root:
                path = self.root / "raw" / "archive_api" / f"thread-{thread_id}" / f"page-{page}.json"
                ensure_dir(path.parent)
                write_json(path, data)
            if not posts:
                break
        return {
            "thread_id": thread_id,
            "title": thread.get("title"),
            "pages": page_count,
            "posts": total_posts,
        }

    def _index_posts(self, store: Store, thread_id: str, thread: dict, posts: list[dict]) -> None:
        assets = []
        links = []
        thread_url = thread.get("originalUrl") or f"https://forums.rpgmakerweb.com/threads/{thread_id}/"
        for post in posts:
            content = post.get("contentHtml") or ""
            if not content:
                continue
            base = post.get("originalUrl") or thread_url
            refs, other = extract_assets(content, base, page_url=base)
            post_id = str(post.get("postId") or "")
            for ref in refs:
                assets.append(
                    {
                        "url": ref.url,
                        "source_url": ref.source_url,
                        "kind": ref.kind,
                        "priority": ref.priority,
                        "status": "pending" if ref.downloadable else "link_only",
                        "thread_id": thread_id,
                        "post_id": post_id,
                        "referer": base,
                    }
                )
            for link in other:
                links.append((base, link.url, "external", link.text))
        if assets:
            store.add_assets(assets)
        if links:
            store.add_links(links)

    def discover_forum(self, store: Store, forum_id: str, with_posts: bool = True,
                       max_threads: int | None = None,
                       max_pages_per_thread: int | None = None,
                       progress=None) -> dict:
        forum_id = parse_forum_id(str(forum_id))
        first = self.forum_threads(forum_id, 1)
        forum = first.get("forum") or {}
        if forum:
            store.upsert_forums([{**forum, "capturedThreadCount": first.get("threadCount")}])
        page_count = int(first.get("pageCount") or 1)
        seen_threads = 0
        fetched_posts = 0
        for page in range(1, page_count + 1):
            data = first if page == 1 else self.forum_threads(forum_id, page)
            threads = data.get("threads") or []
            store.upsert_threads(threads, forum_id=forum_id, source="archive")
            for item in threads:
                tid = str(item.get("threadId") or "")
                if not tid:
                    continue
                seen_threads += 1
                if max_threads and seen_threads > max_threads:
                    seen_threads = max_threads
                    break
                if with_posts:
                    existing = store.thread(tid)
                    if existing and existing["page_count"] and existing["pages_fetched"] >= existing["page_count"]:
                        continue
                    try:
                        result = self.discover_thread(
                            store, tid, max_pages=max_pages_per_thread, save_raw=False
                        )
                        fetched_posts += int(result.get("posts") or 0)
                        if progress:
                            progress(
                                f"forum {forum_id} page {page}: thread {tid} "
                                f"({result.get('pages')} pages, {result.get('posts')} posts)"
                            )
                    except FetchError as exc:
                        if progress:
                            progress(f"forum {forum_id}: thread {tid} failed: {exc}")
            if max_threads and seen_threads >= max_threads:
                break
        return {"forum_id": forum_id, "threads": seen_threads, "posts": fetched_posts}

    def discover_all(self, store: Store, with_posts: bool = True,
                     forum_filter=None, max_threads: int | None = None,
                     max_pages_per_thread: int | None = None, progress=None) -> dict:
        forums = self.forums()
        store.upsert_forums(forums)
        total_threads = 0
        total_posts = 0
        for forum in forums:
            fid = str(forum.get("forumId") or "")
            if not fid:
                continue
            if forum_filter and not forum_filter(forum):
                continue
            if progress:
                progress(f"discovering forum {fid}: {forum.get('title')}")
            remaining = None if max_threads is None else max(0, max_threads - total_threads)
            if remaining == 0:
                break
            result = self.discover_forum(
                store, fid, with_posts=with_posts, max_threads=remaining,
                max_pages_per_thread=max_pages_per_thread, progress=progress,
            )
            total_threads += int(result.get("threads") or 0)
            total_posts += int(result.get("posts") or 0)
        return {"forums": len(forums), "threads": total_threads, "posts": total_posts}
