from __future__ import annotations

import html as html_lib
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Iterable

from .db import Store
from .extract import rewrite_html_urls, strip_scripts
from .util import ensure_dir, human_size, slugify, utc_now, write_json, write_text

POSTS_PER_PAGE = 50
THREADS_PER_FORUM_PAGE = 200
MAX_ASSET_ROWS = 5000

CSS = """
:root {
  color-scheme: light dark;
  --bg: #f7f5ef;
  --panel: #ffffff;
  --ink: #1d1c19;
  --muted: #6b675f;
  --line: #ddd8cc;
  --accent: #7b3f00;
  --accent-2: #0b6b6b;
  --danger: #a12a2a;
  --code: #f0ece2;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #171614;
    --panel: #211f1b;
    --ink: #ece7dc;
    --muted: #a8a196;
    --line: #3a352d;
    --accent: #e0a86a;
    --accent-2: #6fd3cf;
    --danger: #ef8b8b;
    --code: #2b2822;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", "Noto Sans TC", sans-serif;
}
a { color: var(--accent-2); text-decoration-thickness: .08em; text-underline-offset: .16em; }
a:hover { color: var(--accent); }
.topbar {
  display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
  padding: .7rem 1.2rem; background: var(--panel); border-bottom: 1px solid var(--line);
  position: sticky; top: 0; z-index: 5;
}
.topbar a { font-weight: 700; text-decoration: none; }
.topbar .spacer { flex: 1; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 1.2rem; }
h1 { line-height: 1.2; margin: .2rem 0 .4rem; font-size: clamp(1.5rem, 3vw, 2.2rem); }
h2 { margin-top: 2rem; }
.muted { color: var(--muted); }
.small { font-size: .88rem; }
.card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  padding: 1rem 1.1rem; margin: .8rem 0; box-shadow: 0 1px 0 rgba(0,0,0,.03);
}
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .7rem; }
.stat { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: .7rem .8rem; }
.stat b { display: block; font-size: 1.45rem; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: .45rem .5rem; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-size: .82rem; text-transform: uppercase; letter-spacing: .04em; }
.table-wrap { overflow-x: auto; }
.post { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; margin: 1rem 0; overflow: hidden; }
.post-head { display: flex; gap: .8rem; flex-wrap: wrap; align-items: baseline; padding: .6rem .9rem; border-bottom: 1px solid var(--line); background: color-mix(in srgb, var(--panel) 88%, var(--bg)); }
.post-author { font-weight: 700; }
.post-body { padding: .9rem 1rem; overflow-wrap: anywhere; }
.post-body img { max-width: 100%; height: auto; }
.post-body blockquote { margin: .6rem 0; padding: .4rem .8rem; border-left: 3px solid var(--line); color: var(--muted); }
.post-body pre, .post-body code { background: var(--code); border-radius: 6px; }
.post-body pre { padding: .7rem; overflow-x: auto; }
.post-body .bbCodeBlock { margin: .7rem 0; }
.post-body .bbCodeSpoiler-content, .post-body .bbCodeBlock-content { border-left: 2px solid var(--line); padding-left: .7rem; }
.files { padding: .6rem .9rem .8rem; border-top: 1px dashed var(--line); font-size: .92rem; }
.files ul { margin: .3rem 0 0; padding-left: 1.2rem; }
.pager { display: flex; gap: .4rem; flex-wrap: wrap; align-items: center; margin: .8rem 0; }
.pager a, .pager span { padding: .2rem .55rem; border: 1px solid var(--line); border-radius: 7px; text-decoration: none; background: var(--panel); }
.pager .current { background: var(--accent); color: var(--bg); border-color: var(--accent); }
input[type=search] {
  width: 100%; max-width: 36rem; padding: .6rem .8rem; border-radius: 9px;
  border: 1px solid var(--line); background: var(--panel); color: var(--ink); font: inherit;
}
.notice { border-left: 4px solid var(--accent); padding: .6rem .9rem; background: var(--panel); }
.badge { display: inline-block; padding: .05rem .45rem; border: 1px solid var(--line); border-radius: 999px; font-size: .78rem; color: var(--muted); }
.ok { color: var(--accent-2); }
.bad { color: var(--danger); }
footer { color: var(--muted); font-size: .85rem; padding: 2rem 1.2rem; text-align: center; }
@media print { .topbar, .pager, footer { display: none; } .post { break-inside: avoid; } }
"""


def _rel(target: str, from_dir: Path, site: Path) -> str:
    return os.path.relpath(site / target, site / from_dir).replace(os.sep, "/")


def _esc(value) -> str:
    return html_lib.escape(str(value or ""), quote=True)


def _page_shell(title: str, body: str, site: Path, from_dir: Path, extra_head: str = "") -> str:
    css = _rel("style.css", from_dir, site)
    home = _rel("index.html", from_dir, site)
    search = _rel("search.html", from_dir, site)
    forums = _rel("forums.html", from_dir, site)
    assets = _rel("assets.html", from_dir, site)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<link rel="stylesheet" href="{_esc(css)}">
{extra_head}
</head>
<body>
<header class="topbar">
  <a href="{_esc(home)}">xfrescue archive</a>
  <a href="{_esc(forums)}">Forums</a>
  <a href="{_esc(search)}">Search</a>
  <a href="{_esc(assets)}">Assets</a>
  <span class="spacer"></span>
  <span class="muted small">offline copy</span>
</header>
{body}
<footer>
  Generated by xfrescue. Content belongs to the original authors.
  This is a personal preservation copy, not a republication.
</footer>
</body>
</html>
"""


class Builder:
    def __init__(self, store: Store, root: str | Path, search_index: bool = True,
                 log=None):
        self.store = store
        self.root = Path(root)
        self.site = self.root / "site"
        self.search_index = search_index
        self._log = log or (lambda msg: None)
        self.asset_map: dict[str, str] = {}
        self.asset_remote: dict[str, str] = {}
        self.thread_map: dict[str, str] = {}
        self.post_map: dict[str, str] = {}
        self.forum_rows: dict[str, object] = {}
        self.asset_by_post: dict[str, list] = {}

    def build(self) -> dict:
        ensure_dir(self.site)
        ensure_dir(self.site / "threads")
        ensure_dir(self.site / "forums")
        write_text(self.site / "style.css", CSS)
        self._prepare_maps()
        threads = list(self.store.iter_threads())
        self._log(f"building {len(threads)} threads")
        for index, thread in enumerate(threads, start=1):
            self._build_thread(thread)
            if index % 500 == 0:
                self._log(f"built {index}/{len(threads)} thread pages")
        self._build_index()
        self._build_forums()
        self._build_assets()
        if self.search_index:
            self._build_search()
        self._build_manifest()
        return self.store.counts()

    # ------------------------------------------------------------------ maps
    def _forums(self) -> list[dict]:
        forums = [dict(row) for row in self.store.forums()]
        known = {str(f.get("forum_id")) for f in forums}
        for row in self.store.conn.execute(
            "SELECT DISTINCT forum_id FROM threads WHERE forum_id IS NOT NULL AND forum_id<>''"
        ):
            fid = str(row["forum_id"])
            if fid not in known:
                forums.append(
                    {"forum_id": fid, "title": f"Forum {fid}", "url": None}
                )
                known.add(fid)
        return sorted(forums, key=lambda f: (f.get("title") or "").lower())

    def _prepare_maps(self) -> None:
        for forum in self._forums():
            self.forum_rows[str(forum["forum_id"])] = forum
        for thread in self.store.iter_threads():
            tid = str(thread["thread_id"])
            self.thread_map[f"thread:{tid}"] = _thread_index(tid)
            if thread["url"]:
                url = _strip_fragment(thread["url"]).rstrip("/")
                if url:
                    self.thread_map[url] = _thread_index(tid)
                    self.thread_map[url + "/"] = _thread_index(tid)
                    for page in range(2, max(1, int(thread["page_count"] or 1)) + 1):
                        self.thread_map[f"{url}/page-{page}"] = _thread_page(tid, page)
        for asset in self.store.assets():
            self.asset_remote[asset["url"]] = asset["url"]
            if asset["source_url"]:
                self.asset_remote.setdefault(asset["source_url"], asset["url"])
            if asset["post_id"]:
                self.asset_by_post.setdefault(str(asset["post_id"]), []).append(asset)
            if not asset["local_path"]:
                continue
            self.asset_map[asset["url"]] = asset["local_path"]
            if asset["source_url"]:
                self.asset_map.setdefault(asset["source_url"], asset["local_path"])
        for thread in self.store.iter_threads():
            for post in self.store.iter_posts(str(thread["thread_id"])):
                page_no = (int(post["post_index"] or 1) - 1) // POSTS_PER_PAGE + 1
                path = _thread_page(str(thread["thread_id"]), page_no) + f"#post-{post['post_id']}"
                self.post_map[str(post["post_id"])] = path
                self.post_map[f"https://forums.rpgmakerweb.com/goto/post?id={post['post_id']}"] = path
                self.post_map[f"https://forums.rpgmakerweb.com/posts/{post['post_id']}/"] = path

    # --------------------------------------------------------------- threads
    def _build_thread(self, thread) -> None:
        tid = str(thread["thread_id"])
        posts = list(self.store.iter_posts(tid))
        pages = max(1, (len(posts) + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE)
        thread_title = thread["title"] or f"Thread {tid}"
        forum = self.forum_rows.get(str(thread["forum_id"] or ""))
        forum_title = forum["title"] if forum else ""
        thread_dir = Path("threads") / tid

        for page_no in range(1, pages + 1):
            chunk = posts[(page_no - 1) * POSTS_PER_PAGE: page_no * POSTS_PER_PAGE]
            body_parts = ['<main class="wrap">']
            if page_no == 1:
                body_parts.append(self._thread_header(thread, forum_title, len(posts)))
            else:
                body_parts.append(
                    f'<div class="muted small"><a href="{_esc(_rel(_thread_index(tid), thread_dir, self.site))}">'
                    f'{_esc(thread_title)}</a> / page {page_no}</div>'
                )
            body_parts.append(self._thread_pager(tid, page_no, pages))
            if not chunk:
                body_parts.append(
                    '<div class="card notice">No posts have been archived for this thread yet. '
                    f'<a href="{_esc(thread["url"] or "#")}">Open the original</a>.</div>'
                )
            for post in chunk:
                body_parts.append(self._render_post(thread, post, thread_dir))
            body_parts.append(self._thread_pager(tid, page_no, pages))
            body_parts.append("</main>")
            title = f"{thread_title} - page {page_no}" if pages > 1 else thread_title
            html = _page_shell(title, "\n".join(body_parts), self.site, thread_dir)
            out = self.site / thread_dir / (("index" if page_no == 1 else f"page-{page_no}") + ".html")
            ensure_dir(out.parent)
            write_text(out, html)

    def _thread_header(self, thread, forum_title: str, post_count: int) -> str:
        tid = str(thread["thread_id"])
        forum_id = str(thread["forum_id"] or "")
        forum_link = ""
        if forum_id:
            forum_link = (
                f'<a href="{_esc(_rel(f"forums/{forum_id}/index.html", Path("threads") / tid, self.site))}">'
                f'{_esc(forum_title or "Forum " + forum_id)}</a>'
            )
        original = thread["url"] or ""
        return f"""
  <div class="muted small">{forum_link or "Forum"} / thread {_esc(tid)}</div>
  <h1>{_esc(thread["title"] or f"Thread {tid}")}</h1>
  <div class="muted small">
    Started by <b>{_esc(thread["author"] or "unknown")}</b>
    {("&middot; " + _esc(thread["created_at"])) if thread["created_at"] else ""}
    &middot; {post_count} archived posts
    {("&middot; <a href='" + _esc(original) + "'>original thread</a>") if original else ""}
  </div>
  <div class="notice small" style="margin-top:.8rem">
    This is an offline preservation copy of a public forum thread. Images or links that were not
    downloaded may still point at the now-closed site or an external host.
  </div>
"""

    def _thread_pager(self, tid: str, page_no: int, pages: int) -> str:
        if pages <= 1:
            return ""
        parts = []
        for n in range(1, pages + 1):
            if n == page_no:
                parts.append(f'<span class="current">{n}</span>')
            else:
                link = _rel(_thread_page(tid, n), Path("threads") / tid, self.site)
                parts.append(f'<a href="{_esc(link)}">{n}</a>')
        return '<nav class="pager">' + " ".join(parts) + "</nav>"

    def _render_post(self, thread, post, thread_dir: Path) -> str:
        content = post["content_html"] or ""
        if content:
            content = strip_scripts(content)
            content = self._rewrite(content, post["url"] or thread["url"] or "", thread_dir)
        else:
            text = _esc(post["content_text"] or "").replace("\n", "<br>")
            content = f"<p>{text}</p>"
        files = self._render_files(str(post["post_id"]), thread_dir)
        original = post["url"] or ""
        return f"""
<article class="post" id="post-{_esc(post["post_id"])}">
  <header class="post-head">
    <span class="post-author">{_esc(post["author"] or "unknown")}</span>
    <span class="muted small">{_esc(post["posted_at"] or "")}</span>
    <span class="spacer"></span>
    <span class="badge">#{_esc(post["post_index"] or "")}</span>
    {f'<a class="small" href="{_esc(original)}">original</a>' if original else ""}
  </header>
  <div class="post-body">{content}</div>
  {files}
</article>
"""

    def _render_files(self, post_id: str, thread_dir: Path) -> str:
        items = []
        seen = set()
        for asset in self.asset_by_post.get(post_id, []):
            if asset["url"] in seen:
                continue
            seen.add(asset["url"])
            if asset["kind"] == "image" and asset["status"] == "done":
                continue
            label = asset["filename"] or asset["url"].rsplit("/", 1)[-1] or asset["url"]
            status = asset["status"]
            size = human_size(asset["size"]) if asset["size"] else ""
            if status == "done" and asset["local_path"]:
                href = _rel(asset["local_path"], thread_dir, self.site)
                extra = f'<span class="badge ok">saved</span> {_esc(size)}'
            else:
                href = asset["url"]
                extra = f'<span class="badge bad">{_esc(status)}</span>'
            items.append(
                f'<li><a href="{_esc(href)}">{_esc(label)}</a> '
                f'<span class="muted small">{_esc(asset["kind"])} {extra}</span></li>'
            )
        if not items:
            return ""
        return '<div class="files"><b class="small">Files referenced in this post</b><ul>' + "".join(items) + "</ul></div>"

    # ------------------------------------------------------------------ maps
    def _rewrite(self, content: str, base_url: str, thread_dir: Path) -> str:
        def mapper(url: str) -> str | None:
            if url in self.asset_map:
                return _rel(self.asset_map[url], thread_dir, self.site)
            if url in self.asset_remote:
                return self.asset_remote[url]
            if url in self.thread_map:
                return _rel(self.thread_map[url], thread_dir, self.site)
            if url in self.post_map:
                return _rel(self.post_map[url], thread_dir, self.site)
            return None

        return rewrite_html_urls(content, mapper, base_url)

    # ----------------------------------------------------------------- index
    def _build_index(self) -> None:
        counts = self.store.counts()
        forums = self._forums()
        top_threads = list(
            self.store.conn.execute(
                "SELECT * FROM threads WHERE last_post_at IS NOT NULL "
                "ORDER BY last_post_at DESC LIMIT 30"
            )
        )
        forum_rows = []
        for forum in forums:
            fid = str(forum["forum_id"])
            nthreads = self.store.conn.execute(
                "SELECT COUNT(*) FROM threads WHERE forum_id=?", (fid,)
            ).fetchone()[0]
            forum_rows.append(
                f'<tr><td><a href="{_esc(_rel(f"forums/{fid}/index.html", Path("."), self.site))}">'
                f'{_esc(forum["title"] or "Forum " + fid)}</a></td>'
                f'<td>{nthreads}</td><td class="small muted">{_esc(forum["url"] or "")}</td></tr>'
            )
        recent_rows = []
        for thread in top_threads:
            tid = str(thread["thread_id"])
            recent_rows.append(
                f'<tr><td><a href="{_esc(_rel(_thread_index(tid), Path("."), self.site))}">'
                f'{_esc(thread["title"] or "Thread " + tid)}</a></td>'
                f'<td class="small">{_esc(thread["author"] or "")}</td>'
                f'<td class="small muted">{_esc(thread["last_post_at"] or "")}</td></tr>'
            )
        body = f"""
<main class="wrap">
  <h1>RPG Maker Web forum archive</h1>
  <p class="muted">A local, browsable copy of public threads and files. Built with xfrescue.</p>
  <div class="stats">
    <div class="stat"><b>{counts["threads"]:,}</b><span class="muted">threads</span></div>
    <div class="stat"><b>{counts["posts"]:,}</b><span class="muted">posts</span></div>
    <div class="stat"><b>{counts["assets"]:,}</b><span class="muted">asset references</span></div>
    <div class="stat"><b>{counts["assets_done"]:,}</b><span class="muted">files saved</span></div>
    <div class="stat"><b>{human_size(counts["asset_bytes"])}</b><span class="muted">downloaded</span></div>
    <div class="stat"><b>{counts["forums"]:,}</b><span class="muted">forums</span></div>
  </div>
  <div class="card notice">
    <b>Read this first.</b> This archive only contains public pages that were fetched. Private
    messages, login-only attachments, and features that needed a live server are not included.
    External links may be dead; saved files show a green <span class="badge ok">saved</span> badge.
  </div>
  <p><a href="{_esc(_rel("search.html", Path("."), self.site))}">Search the archive</a>
     &middot; <a href="{_esc(_rel("assets.html", Path("."), self.site))}">Asset browser</a>
     &middot; <a href="{_esc(_rel("manifest.json", Path("."), self.site))}">manifest.json</a></p>
  <h2>Recent threads</h2>
  <div class="card table-wrap"><table>
    <thead><tr><th>Thread</th><th>Author</th><th>Last post</th></tr></thead>
    <tbody>{''.join(recent_rows) or '<tr><td colspan="3">No threads yet.</td></tr>'}</tbody>
  </table></div>
  <h2>Forums</h2>
  <div class="card table-wrap"><table>
    <thead><tr><th>Forum</th><th>Threads</th><th>Original URL</th></tr></thead>
    <tbody>{''.join(forum_rows) or '<tr><td colspan="3">No forums yet.</td></tr>'}</tbody>
  </table></div>
</main>
"""
        write_text(self.site / "index.html", _page_shell("RPG Maker Web archive", body, self.site, Path(".")))

    def _build_forums(self) -> None:
        for forum in self._forums():
            fid = str(forum["forum_id"])
            total = self.store.conn.execute(
                "SELECT COUNT(*) FROM threads WHERE forum_id=?", (fid,)
            ).fetchone()[0]
            pages = max(1, (total + THREADS_PER_FORUM_PAGE - 1) // THREADS_PER_FORUM_PAGE)
            for page_no in range(1, pages + 1):
                rows = self.store.conn.execute(
                    "SELECT * FROM threads WHERE forum_id=? "
                    "ORDER BY COALESCE(last_post_at, created_at) DESC LIMIT ? OFFSET ?",
                    (fid, THREADS_PER_FORUM_PAGE, (page_no - 1) * THREADS_PER_FORUM_PAGE),
                ).fetchall()
                forum_dir = Path("forums") / fid
                body_rows = []
                for thread in rows:
                    tid = str(thread["thread_id"])
                    body_rows.append(
                        f'<tr><td><a href="{_esc(_rel(_thread_index(tid), forum_dir, self.site))}">'
                        f'{_esc(thread["title"] or "Thread " + tid)}</a></td>'
                        f'<td class="small">{_esc(thread["author"] or "")}</td>'
                        f'<td class="small">{thread["post_count"] or thread["reply_count"] or ""}</td>'
                        f'<td class="small muted">{_esc(thread["last_post_at"] or "")}</td></tr>'
                    )
                pager = []
                if pages > 1:
                    for n in range(1, pages + 1):
                        if n == page_no:
                            pager.append(f'<span class="current">{n}</span>')
                        else:
                            target = f"forums/{fid}/" + (("index" if n == 1 else f"page-{n}") + ".html")
                            pager.append(f'<a href="{_esc(_rel(target, forum_dir, self.site))}">{n}</a>')
                body = f"""
<main class="wrap">
  <div class="muted small"><a href="{_esc(_rel("forums.html", forum_dir, self.site))}">Forums</a> / {_esc(forum["title"] or "Forum " + fid)}</div>
  <h1>{_esc(forum["title"] or "Forum " + fid)}</h1>
  <p class="muted small">{total:,} threads. {("Original: <a href='" + _esc(forum["url"]) + "'>" + _esc(forum["url"]) + "</a>") if forum["url"] else ""}</p>
  <div class="card table-wrap"><table>
    <thead><tr><th>Thread</th><th>Author</th><th>Posts</th><th>Last post</th></tr></thead>
    <tbody>{''.join(body_rows) or '<tr><td colspan="4">No threads archived.</td></tr>'}</tbody>
  </table></div>
  {('<nav class="pager">' + ' '.join(pager) + '</nav>') if pager else ''}
</main>
"""
                out = self.site / forum_dir / (("index" if page_no == 1 else f"page-{page_no}") + ".html")
                ensure_dir(out.parent)
                write_text(out, _page_shell(forum["title"] or f"Forum {fid}", body, self.site, forum_dir))

        # A single forum directory page for the top nav.
        rows = []
        for forum in self._forums():
            fid = str(forum["forum_id"])
            n = self.store.conn.execute(
                "SELECT COUNT(*) FROM threads WHERE forum_id=?", (fid,)
            ).fetchone()[0]
            rows.append(
                f'<tr><td><a href="{_esc(_rel(f"forums/{fid}/index.html", Path("."), self.site))}">'
                f'{_esc(forum["title"] or "Forum " + fid)}</a></td><td>{n}</td></tr>'
            )
        body = f"""
<main class="wrap">
  <h1>Forums</h1>
  <div class="card table-wrap"><table><thead><tr><th>Forum</th><th>Threads</th></tr></thead>
  <tbody>{''.join(rows) or '<tr><td colspan="2">No forums yet.</td></tr>'}</tbody></table></div>
</main>
"""
        write_text(self.site / "forums.html", _page_shell("Forums", body, self.site, Path(".")))

    # ---------------------------------------------------------------- assets
    def _build_assets(self) -> None:
        assets = self.store.assets()
        counts = {}
        for asset in assets:
            counts[asset["status"]] = counts.get(asset["status"], 0) + 1
        rows = []
        for asset in assets[:MAX_ASSET_ROWS]:
            if asset["local_path"]:
                href = _rel(asset["local_path"], Path("."), self.site)
                link = f'<a href="{_esc(href)}">{_esc(asset["filename"] or "file")}</a>'
            else:
                link = f'<a href="{_esc(asset["url"])}">{_esc(asset["filename"] or asset["url"])}</a>'
            rows.append(
                f'<tr><td>{link}</td><td class="small">{_esc(asset["kind"])}</td>'
                f'<td class="small">{_esc(asset["status"])}</td>'
                f'<td class="small">{_esc(human_size(asset["size"]))}</td>'
                f'<td class="small"><a href="{_esc(asset["url"])}">source</a></td></tr>'
            )
        body = f"""
<main class="wrap">
  <h1>Assets</h1>
  <p class="muted">All asset references discovered in archived posts.
     Status counts: {", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))}.
     Full list: <a href="{_esc(_rel("assets.csv", Path("."), self.site))}">assets.csv</a>.</p>
  <div class="card table-wrap"><table>
    <thead><tr><th>File</th><th>Kind</th><th>Status</th><th>Size</th><th>Source</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="5">No assets discovered.</td></tr>'}</tbody>
  </table></div>
  {f'<p class="muted small">Showing the first {MAX_ASSET_ROWS:,} rows; use assets.csv for all {len(assets):,}.</p>' if len(assets) > MAX_ASSET_ROWS else ''}
</main>
"""
        write_text(self.site / "assets.html", _page_shell("Assets", body, self.site, Path(".")))
        self.store.export_assets_csv(self.site / "assets.csv")

    # ---------------------------------------------------------------- search
    def _build_search(self) -> None:
        threads = []
        posts = []
        for thread in self.store.iter_threads():
            tid = str(thread["thread_id"])
            title = thread["title"] or f"Thread {tid}"
            forum = thread["forum_id"] or ""
            first = self.store.conn.execute(
                "SELECT content_text FROM posts WHERE thread_id=? ORDER BY post_index LIMIT 1",
                (tid,),
            ).fetchone()
            text = (first["content_text"] if first else "") or ""
            threads.append(
                {
                    "kind": "thread",
                    "id": tid,
                    "title": title,
                    "forum": forum,
                    "author": thread["author"] or "",
                    "url": _thread_index(tid),
                    "text": text[:240],
                }
            )
            for post in self.store.iter_posts(tid):
                body_text = (post["content_text"] or "").strip()
                if not body_text and post["content_html"]:
                    body_text = re.sub(r"<[^>]+>", " ", post["content_html"])
                    body_text = html_lib.unescape(body_text)
                    body_text = re.sub(r"\s+", " ", body_text).strip()
                if not body_text:
                    continue
                page_no = (int(post["post_index"] or 1) - 1) // POSTS_PER_PAGE + 1
                posts.append(
                    {
                        "kind": "post",
                        "id": str(post["post_id"]),
                        "index": int(post["post_index"] or 0),
                        "title": title,
                        "forum": forum,
                        "author": post["author"] or "",
                        "posted": post["posted_at"] or "",
                        "url": _thread_page(tid, page_no) + f"#post-{post['post_id']}",
                        "text": body_text[:240],
                    }
                )
        write_json(self.site / "search.json", {"threads": threads, "posts": posts})
        body = """
<main class="wrap">
  <h1>Search</h1>
  <p class="muted">Search thread titles, authors, and all archived post text.</p>
  <input id="q" type="search" placeholder="type to filter..." autofocus>
  <p id="count" class="muted small"></p>
  <div id="results"></div>
</main>
<script>
const input = document.getElementById('q');
const results = document.getElementById('results');
const count = document.getElementById('count');
let threads = [];
let posts = [];
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function matched(items, q, limit) {
  const hits = [];
  for (const t of items) {
    const hay = (t.title + ' ' + t.author + ' ' + t.text).toLowerCase();
    if (hay.includes(q)) hits.push(t);
    if (hits.length >= limit) break;
  }
  return hits;
}
function render() {
  const q = input.value.trim().toLowerCase();
  if (!q) { results.innerHTML = '<p class="muted">Start typing to search.</p>'; count.textContent = ''; return; }
  const th = matched(threads, q, 150);
  const po = matched(posts, q, 150);
  const hits = th.concat(po);
  count.textContent = th.length + ' thread(s), ' + po.length + ' post(s)' +
    (th.length >= 150 || po.length >= 150 ? ' (showing first 150 of each)' : '');
  results.innerHTML = hits.map(t => {
    const kind = t.kind === 'post' ? 'post #' + esc(String(t.index)) : 'thread';
    const who = t.kind === 'post' && t.posted
      ? esc(t.author || 'unknown') + ' · ' + esc(t.posted)
      : esc(t.author || 'unknown') + ' · forum ' + esc(t.forum);
    return '<div class="card"><a href="' + encodeURI(t.url) + '"><b>' + esc(t.title) + '</b></a> ' +
      '<span class="badge">' + kind + '</span>' +
      '<div class="small muted">' + who + '</div>' +
      '<div class="small">' + esc(t.text) + '</div></div>';
  }).join('') || '<p class="muted">No matches.</p>';
}
fetch('search.json').then(r => r.json()).then(d => {
  threads = d.threads || [];
  posts = d.posts || [];
  render();
}).catch(() => { results.innerHTML = '<p class="bad">search.json is missing.</p>'; });
input.addEventListener('input', render);
</script>
"""
        write_text(self.site / "search.html", _page_shell("Search", body, self.site, Path(".")))

    # -------------------------------------------------------------- manifest
    def _build_manifest(self) -> None:
        counts = self.store.counts()
        manifest = {
            "format": "xfrescue-archive-v1",
            "generated_at": utc_now(),
            "tool": "xfrescue",
            "counts": counts,
            "source": self.store.get_meta("source"),
            "scope": self.store.get_meta("scope"),
            "paths": {
                "threads": "threads/",
                "assets": "assets/",
                "raw": "../raw/",
                "csv": "assets.csv",
                "search": "search.json",
            },
        }
        write_json(self.site / "manifest.json", manifest)
        write_text(
            self.site / "README.txt",
            "xfrescue offline archive\n"
            "========================\n\n"
            "Open index.html in a browser. Nothing here needs a server.\n\n"
            "This archive was built from public forum content. Copyright remains with the\n"
            "original authors. Do not redistribute content you do not have rights to.\n"
            "Private messages, login-only attachments, and live features are not included.\n\n"
            f"Threads: {counts['threads']}\nPosts: {counts['posts']}\n"
            f"Assets recorded: {counts['assets']}\nFiles saved: {counts['assets_done']}\n",
        )


def _thread_index(tid: str) -> str:
    return f"threads/{tid}/index.html"


def _thread_page(tid: str, page: int) -> str:
    return f"threads/{tid}/" + ("index.html" if page == 1 else f"page-{page}.html")


def _strip_fragment(url: str) -> str:
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
