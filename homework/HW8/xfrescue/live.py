from __future__ import annotations

import html as html_lib
import re
import urllib.parse
from pathlib import Path

from .db import Store
from .extract import extract_assets
from .net import FetchError, HttpClient
from .util import ensure_dir, normalize_url, safe_filename, write_text

LIVE_BASE = "https://forums.rpgmakerweb.com"

ARTICLE_TAG_RE = re.compile(r"<(/?)article\b([^>]*)>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
TIME_RE = re.compile(r'<time\b[^>]*\bdatetime="([^"]+)"', re.I)
AUTHOR_RE = re.compile(r'\bdata-author="([^"]*)"', re.I)
POST_ID_RE = re.compile(r'\bid="js-post-(\d+)"', re.I)
TITLE_RE = re.compile(r'<h1[^>]*class="[^"]*p-title-value[^"]*"[^>]*>(.*?)</h1>', re.I | re.S)
FORUM_TITLE_RE = re.compile(
    r'<a href="/forums/[^"]+"[^>]*>\s*<span itemprop="name">(.*?)</span>', re.I | re.S
)
CONTAINER_KEY_RE = re.compile(r'data-container-key="node-(\d+)"', re.I)
NEXT_RE = re.compile(r'<link\b[^>]*\brel="next"[^>]*\bhref="([^"]+)"', re.I)
PAGE_JUMP_RE = re.compile(r'<input\b[^>]*class="[^"]*js-pageJumpPage[^"]*"[^>]*>', re.I)
THREAD_LINK_RE = re.compile(r'<a\b[^>]*href="(/threads/[^"#?]+?\.(\d+)/?)"[^>]*>(.*?)</a>', re.I | re.S)
THREAD_URL_RE = re.compile(r"^/threads/[^/?#]+?\.(\d+)(?:/|$)")
FORUM_URL_RE = re.compile(r"^/forums/[^/?#]+?\.(\d+)(?:/|$)")


def strip_tags(value: str) -> str:
    text = TAG_RE.sub(" ", value or "")
    text = html_lib.unescape(text)
    return " ".join(text.split())


def parse_page_count(html: str) -> int:
    for tag in PAGE_JUMP_RE.findall(html or ""):
        match = re.search(r'\bmax="(\d+)"', tag, re.I)
        if match:
            return int(match.group(1))
    match = re.search(r"\bof\s+(\d+)\s*</span>", html or "", re.I)
    if match:
        return int(match.group(1))
    return 1


def parse_next_url(html: str, page_url: str) -> str | None:
    match = NEXT_RE.search(html or "")
    if match:
        return normalize_url(html_lib.unescape(match.group(1)), page_url)
    return None


def _attrs(tag: str) -> dict[str, str]:
    result = {}
    for match in re.finditer(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))', tag):
        name = match.group(1).lower()
        value = match.group(3) if match.group(3) is not None else (
            match.group(4) if match.group(4) is not None else match.group(5)
        )
        result[name] = html_lib.unescape(value or "")
    return result


def _balanced_div(html: str, start: int) -> str | None:
    open_re = re.compile(r"<div\b", re.I)
    close_re = re.compile(r"</div\s*>", re.I)
    depth = 0
    pos = start
    while pos < len(html):
        m_open = open_re.search(html, pos)
        m_close = close_re.search(html, pos)
        if not m_close:
            return None
        if m_open and m_open.start() < m_close.start():
            depth += 1
            pos = m_open.end()
        else:
            depth -= 1
            pos = m_close.end()
            if depth == 0:
                # start tag ends after the first '>'
                first_end = html.find(">", start)
                return html[first_end + 1: m_close.start()]
    return None


def parse_live_posts(html: str, page_url: str, page_no: int = 1,
                     per_page: int = 20) -> list[dict]:
    articles = []
    depth = 0
    start = None
    start_attrs = ""
    for match in ARTICLE_TAG_RE.finditer(html or ""):
        closing, attrs = match.group(1), match.group(2)
        if not closing:
            if depth == 0:
                start = match.start()
                start_attrs = attrs
            depth += 1
        else:
            depth -= 1
            if depth == 0 and start is not None:
                articles.append((start, match.end(), start_attrs))
                start = None
                start_attrs = ""

    posts = []
    for index, (a_start, a_end, attrs_text) in enumerate(articles, start=1):
        attrs = _attrs(attrs_text)
        classes = attrs.get("class", "")
        if "message" not in classes or "js-post" not in classes:
            continue
        article = html[a_start:a_end]
        post_id = attrs.get("id", "")
        match = re.search(r"js-post-(\d+)", post_id)
        post_id = match.group(1) if match else ""
        if not post_id:
            continue
        number_match = re.search(r">\s*#(\d+)\s*</a>", article)
        if number_match:
            post_index = int(number_match.group(1))
        else:
            post_index = (max(0, page_no - 1) * per_page) + index
        body = ""
        body_match = re.search(r'<div\b[^>]*class="[^"]*\bbbWrapper\b[^"]*"[^>]*>', article, re.I)
        if body_match:
            body = _balanced_div(article, body_match.start()) or ""
        if not body:
            body = ""
        time_match = TIME_RE.search(article)
        posts.append(
            {
                "postId": post_id,
                "postIndex": post_index,
                "authorName": attrs.get("data-author"),
                "postedAt": time_match.group(1) if time_match else None,
                "contentHtml": body,
                "contentText": strip_tags(body),
                "originalUrl": f"{page_url.split('#')[0]}#post-{post_id}",
            }
        )
    return posts


def _raw_path(root: Path, url: str) -> Path:
    parts = urllib.parse.urlsplit(url)
    segments = [safe_filename(s, fallback="index") for s in parts.path.split("/") if s]
    if not segments:
        segments = ["index"]
    if parts.query:
        segments[-1] += "-" + safe_filename(parts.query, fallback="q")[:40]
    if not segments[-1].lower().endswith((".html", ".htm")):
        segments.append("index.html")
    return root / "raw" / "live" / safe_filename(parts.netloc) / Path(*segments)


class LiveForum:
    def __init__(self, client: HttpClient, root: str | Path, base: str = LIVE_BASE):
        self.client = client
        self.root = Path(root)
        self.base = base.rstrip("/")

    def discover_thread_url(self, store: Store, url: str, max_pages: int | None = None,
                            force: bool = False, save_raw: bool = True) -> dict:
        url = normalize_url(url)
        if not url:
            raise ValueError(f"invalid thread URL: {url}")
        match = THREAD_URL_RE.search(urllib.parse.urlsplit(url).path)
        if not match:
            raise ValueError(f"not a XenForo thread URL: {url}")
        thread_id = match.group(1)
        existing = store.thread(thread_id)
        if (not force and existing and existing["page_count"]
                and existing["pages_fetched"] >= existing["page_count"]):
            return {
                "thread_id": thread_id,
                "title": existing["title"],
                "pages": existing["page_count"],
                "posts": 0,
                "skipped": True,
            }

        page_url = url
        page_no = 0
        pages_fetched = 0
        total_posts = 0
        page_count = 1
        title = existing["title"] if existing else None
        while page_url:
            page_no += 1
            if max_pages and page_no > max_pages:
                break
            resp = self.client.get(page_url)
            html = resp.body.decode("utf-8", "replace")
            final_url = resp.url
            page_count = max(page_count, parse_page_count(html))
            if page_no == 1:
                title_match = TITLE_RE.search(html)
                if title_match:
                    title = strip_tags(title_match.group(1))
                container = CONTAINER_KEY_RE.search(html)
                forum_id = container.group(1) if container else None
                forum_title_match = FORUM_TITLE_RE.search(html)
                if forum_id:
                    store.upsert_forums(
                        [{
                            "forumId": forum_id,
                            "title": strip_tags(forum_title_match.group(1)) if forum_title_match else None,
                        }]
                    )
                posts = parse_live_posts(html, final_url, page_no=page_no)
                if posts:
                    author = posts[0].get("authorName")
                    created = posts[0].get("postedAt")
                else:
                    author = created = None
                store.upsert_threads(
                    [{
                        "threadId": thread_id,
                        "forumId": forum_id,
                        "title": title,
                        "authorName": author,
                        "createdAt": created,
                        "lastPostAt": posts[-1].get("postedAt") if posts else None,
                        "originalUrl": url,
                        "pageCount": page_count,
                    }],
                    forum_id=forum_id,
                    source="live",
                )
            else:
                posts = parse_live_posts(html, final_url, page_no=page_no)
            if page_no > 1:
                # XenForo "article" threads repeat the first post at the top of every
                # page. It is already stored from page 1, so don't renumber it.
                posts = [p for p in posts if store.post(str(p.get("postId"))) is None]
            for post in posts:
                post["threadId"] = thread_id
            total_posts += store.upsert_posts(posts, source="live")
            self._index_page(store, thread_id, html, final_url)
            if save_raw:
                path = _raw_path(self.root, final_url)
                ensure_dir(path.parent)
                write_text(path, html)
            pages_fetched = page_no
            store.set_thread_pages(thread_id, pages_fetched, page_count)
            page_url = parse_next_url(html, final_url)
        return {
            "thread_id": thread_id,
            "title": title,
            "pages": pages_fetched,
            "posts": total_posts,
        }

    def discover_forum_url(self, store: Store, url: str, with_posts: bool = False,
                           max_pages: int | None = None, max_threads: int | None = None,
                           save_raw: bool = True) -> dict:
        url = normalize_url(url)
        if not url:
            raise ValueError(f"invalid forum URL: {url}")
        match = FORUM_URL_RE.search(urllib.parse.urlsplit(url).path)
        if not match:
            raise ValueError(f"not a XenForo forum URL: {url}")
        forum_id = match.group(1)
        page_url = url
        page_no = 0
        threads_seen = 0
        total_posts = 0
        while page_url:
            page_no += 1
            if max_pages and page_no > max_pages:
                break
            resp = self.client.get(page_url)
            html = resp.body.decode("utf-8", "replace")
            final_url = resp.url
            if page_no == 1:
                forum_match = FORUM_TITLE_RE.search(html)
                store.upsert_forums(
                    [{
                        "forumId": forum_id,
                        "title": strip_tags(forum_match.group(1)) if forum_match else None,
                        "originalUrl": url,
                    }]
                )
            batch = []
            for link in THREAD_LINK_RE.finditer(html):
                href, tid, inner = link.group(1), link.group(2), link.group(3)
                thread_url = normalize_url(href, final_url)
                if not thread_url:
                    continue
                batch.append(
                    {
                        "threadId": tid,
                        "title": strip_tags(inner),
                        "originalUrl": thread_url,
                    }
                )
            if batch:
                store.upsert_threads(batch, forum_id=forum_id, source="live")
            if with_posts:
                seen = set()
                for item in batch:
                    if item["threadId"] in seen:
                        continue
                    seen.add(item["threadId"])
                    threads_seen += 1
                    if max_threads and threads_seen > max_threads:
                        threads_seen = max_threads
                        break
                    result = self.discover_thread_url(
                        store, item["originalUrl"], force=False, save_raw=save_raw
                    )
                    total_posts += int(result.get("posts") or 0)
            if save_raw:
                path = _raw_path(self.root, final_url)
                ensure_dir(path.parent)
                write_text(path, html)
            page_url = parse_next_url(html, final_url)
            if max_threads and threads_seen >= max_threads:
                break
        return {"forum_id": forum_id, "threads": threads_seen, "posts": total_posts, "pages": page_no}

    def _index_page(self, store: Store, thread_id: str, html: str, page_url: str) -> None:
        assets, links = extract_assets(html, page_url, page_url=page_url)
        rows = []
        for ref in assets:
            rows.append(
                {
                    "url": ref.url,
                    "source_url": ref.source_url,
                    "kind": ref.kind,
                    "priority": ref.priority,
                    "status": "pending" if ref.downloadable else "link_only",
                    "thread_id": thread_id,
                    "post_id": None,
                    "referer": page_url,
                }
            )
        if rows:
            store.add_assets(rows)
        if links:
            store.add_links([(page_url, link.url, "external", link.text) for link in links])
