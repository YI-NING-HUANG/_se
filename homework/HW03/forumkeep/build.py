from __future__ import annotations

import html as html_lib
import json
import os
import posixpath
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Callable, Iterable

from . import __version__
from .download import asset_output_name
from .htmlx import extract_css_urls, parse_srcset, srcset_value
from .store import Store
from .util import (
    decode_bytes,
    ensure_dir,
    human_size,
    normalize_url,
    safe_filename,
    split_fragment,
    url_hash,
    utc_now,
    write_text,
)

ATTR_URL_RE = re.compile(
    r'(?P<name>\b(?:href|src|poster|data-src|data-original|data-lazy-src|background)\s*=\s*)'
    r'(?P<quote>["\'])(?P<url>.*?)(?P=quote)',
    re.I | re.S,
)
SRCSET_RE = re.compile(
    r'(?P<name>\b(?:srcset|data-srcset|data-lazy-srcset)\s*=\s*)'
    r'(?P<quote>["\'])(?P<value>.*?)(?P=quote)',
    re.I | re.S,
)
BASE_RE = re.compile(r"<base\b[^>]*>", re.I)
BODY_RE = re.compile(r"(<body\b[^>]*>)", re.I)
HEAD_RE = re.compile(r"(<head\b[^>]*>)", re.I)
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.I | re.S)
SCRIPT_SELF_RE = re.compile(r"<script\b[^>]*/\s*>", re.I)
EVENT_ATTR_RE = re.compile(
    r"\s+on[A-Za-z0-9_-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I
)
INTEGRITY_ATTR_RE = re.compile(
    r"\s+(?:integrity|nonce)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I
)
CSP_META_RE = re.compile(
    r"<meta\b[^>]*http-equiv\s*=\s*[\"']?Content-Security-Policy[\"']?[^>]*>",
    re.I | re.S,
)
CHARSET_META_RE = re.compile(r"<meta\b[^>]*charset\s*=\s*[\"']?[^\"'\s/>]+[\"']?[^>]*>", re.I)
CONTENT_TYPE_META_RE = re.compile(
    r"(<meta\b[^>]*http-equiv\s*=\s*[\"']?Content-Type[\"']?[^>]*content\s*=\s*[\"'][^\"']*charset=)"
    r"[^\"';]+",
    re.I,
)
STYLE_ATTR_RE = re.compile(
    r"(?P<prefix>\bstyle\s*=\s*)(?P<quote>[\"'])(?P<css>.*?)(?P=quote)",
    re.I | re.S,
)
STYLE_BLOCK_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.I | re.S)
CSS_CHARSET_RE = re.compile(r"@charset\s+[\"'][^\"']+[\"']\s*;", re.I)
CSS_IMPORT_QUOTED_RE = re.compile(
    r"(@import\s+)([\"'])(.*?)\2", re.I
)

SITE_CSS = """
:root{color-scheme:light;--ink:#22252a;--muted:#6c7280;--line:#dfe3e8;--soft:#f6f7f9;--accent:#28666e;--accent-soft:#e7f1f2}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC","Microsoft JhengHei",sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header.site{background:var(--soft);border-bottom:1px solid var(--line);padding:1.2rem 1.5rem}
header.site .wrap{max-width:1120px;margin:0 auto}
header.site h1{margin:0;font-size:1.45rem}
header.site p{margin:.3rem 0 0;color:var(--muted)}
main{max-width:1120px;margin:0 auto;padding:1.5rem}
nav.site{display:flex;flex-wrap:wrap;gap:.5rem 1.1rem;margin-top:.8rem}
nav.site a{font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.8rem;margin:1.2rem 0}
.card{border:1px solid var(--line);border-radius:10px;padding:1rem;background:#fff}
.card .num{font-size:1.7rem;font-weight:700;color:var(--accent)}
.card .label{color:var(--muted);font-size:.9rem}
table{width:100%;border-collapse:collapse;font-size:.94rem}
th,td{border-bottom:1px solid var(--line);padding:.5rem .55rem;text-align:left;vertical-align:top}
th{background:var(--soft)}
tr:hover td{background:#fafbfc}
.meta{color:var(--muted);font-size:.88rem}
.notice{border-left:4px solid var(--accent);background:var(--accent-soft);padding:.8rem 1rem;margin:1rem 0}
.pager{display:flex;gap:1rem;justify-content:center;margin:1.5rem 0;flex-wrap:wrap}
.thumb{width:64px;height:64px;object-fit:cover;border-radius:6px;border:1px solid var(--line);background:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.8rem}
.asset{border:1px solid var(--line);border-radius:8px;padding:.6rem;min-width:0}
.asset img{width:100%;height:150px;object-fit:contain;background:var(--soft);border-radius:5px}
.asset .name{font-size:.85rem;overflow-wrap:anywhere}
input[type=search]{width:100%;padding:.75rem 1rem;border:1px solid var(--line);border-radius:8px;font:inherit}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--soft);padding:1rem;border-radius:8px}
footer.site{max-width:1120px;margin:2rem auto 0;padding:1.2rem 1.5rem 2rem;color:var(--muted);font-size:.85rem;border-top:1px solid var(--line)}
@media(max-width:640px){main{padding:1rem}header.site{padding:1rem}th,td{padding:.4rem}}
""".strip()


def page_site_path(url: str) -> str:
    host = safe_filename(urllib.parse.urlsplit(url).hostname or "site", fallback="site")
    return f"pages/{host}/{url_hash(url, 12)}.html"


def asset_site_path(asset) -> str:
    filename = asset_output_name(asset)
    sha = asset["sha256"] or "unknown"
    return f"assets/{sha[:2]}/{filename}"


def link_path(target: str, current: str) -> str:
    relative = posixpath.relpath(target, posixpath.dirname(current) or ".")
    return urllib.parse.quote(relative, safe="/#")


def build_site(
    store: Store,
    *,
    banner: bool = True,
    strip_scripts: bool = True,
    log: Callable[[str], None] | None = None,
) -> dict:
    log = log or (lambda message: None)
    site_dir = store.root / "site"
    if site_dir.exists():
        shutil.rmtree(site_dir)
    ensure_dir(site_dir)
    pages = store.pages()
    asset_rows = store.assets()
    done_assets = [asset for asset in asset_rows if asset["status"] == "done"]
    usable_pages = [
        page for page in pages
        if page["raw_path"] and (store.root / page["raw_path"]).exists()
    ]
    usable_assets = [
        asset for asset in done_assets
        if asset["local_path"] and (store.root / asset["local_path"]).exists()
    ]
    aliases = store.alias_map()
    page_map: dict[str, str] = {}
    for page in usable_pages:
        target = page_site_path(page["url"])
        page_map[page["url"]] = target
        if page["final_url"]:
            page_map[page["final_url"]] = target
    for alias, target_url in aliases.items():
        if target_url in page_map:
            page_map[alias] = page_map[target_url]
    asset_map: dict[str, str] = {}
    for asset in usable_assets:
        target = asset_site_path(asset)
        asset_map[asset["url"]] = target
        if asset["final_url"]:
            asset_map[asset["final_url"]] = target

    copied_assets = 0
    missing_blobs = len(done_assets) - len(usable_assets)
    for asset in usable_assets:
        source = store.root / asset["local_path"]
        destination = site_dir / asset_site_path(asset)
        ensure_dir(destination.parent)
        if (asset["kind"] == "stylesheet" or (asset["content_type"] or "").startswith("text/css")):
            data = source.read_bytes()
            text, _encoding = decode_bytes(data, asset["content_type"] or "text/css")
            text = rewrite_css(
                text,
                base_url=asset["final_url"] or asset["url"],
                current_rel=asset_site_path(asset),
                asset_map=asset_map,
            )
            text = CSS_CHARSET_RE.sub('@charset "UTF-8";', text, count=1)
            write_text(destination, text)
        else:
            shutil.copyfile(source, destination)
        copied_assets += 1

    built_pages = 0
    for page in usable_pages:
        raw_path = store.root / page["raw_path"]
        raw = raw_path.read_bytes()
        text, encoding = decode_bytes(
            raw, page["content_type"] or "", head=raw[:8192]
        )
        if page["encoding"]:
            try:
                text = raw.decode(page["encoding"])
                encoding = page["encoding"]
            except (UnicodeDecodeError, LookupError):
                pass
        current_rel = page_site_path(page["url"])
        rewritten = rewrite_html(
            text,
            page_url=page["final_url"] or page["url"],
            base_url=page["base_url"] or page["final_url"] or page["url"],
            current_rel=current_rel,
            page_map=page_map,
            asset_map=asset_map,
            banner=banner,
            strip_scripts=strip_scripts,
        )
        destination = site_dir / current_rel
        ensure_dir(destination.parent)
        write_text(destination, rewritten)
        built_pages += 1

    write_text(site_dir / "style.css", SITE_CSS)
    write_index(store, site_dir, usable_pages, asset_rows)
    write_page_listings(site_dir, usable_pages)
    write_asset_listing(site_dir, usable_assets)
    write_search(site_dir, usable_pages)
    write_manifest(store, site_dir, usable_pages, usable_assets)
    write_site_readme(store, site_dir)
    summary = {
        "pages": built_pages,
        "assets_copied": copied_assets,
        "assets_pending": sum(1 for asset in asset_rows if asset["status"] == "pending"),
        "assets_error": sum(
            1 for asset in asset_rows if asset["status"] in {"error", "blocked"}
        ),
        "missing_blobs": missing_blobs,
        "site": str(site_dir),
    }
    store.set_meta("last_build", summary)
    store.set_meta("last_build_at", utc_now())
    log(
        f"built {built_pages} pages and {copied_assets} files into {site_dir}"
    )
    return summary


def rewrite_html(
    html: str,
    *,
    page_url: str,
    base_url: str,
    current_rel: str,
    page_map: dict[str, str],
    asset_map: dict[str, str],
    banner: bool,
    strip_scripts: bool,
) -> str:
    base = base_url or page_url

    def replace_url(raw: str) -> str:
        return _resolve_ref(
            raw, base, current_rel, page_map, asset_map, strip_scripts=strip_scripts
        )

    def attr_callback(match: re.Match) -> str:
        name = match.group("name")
        quote = match.group("quote")
        raw = match.group("url")
        return f"{name}{quote}{replace_url(raw)}{quote}"

    html = ATTR_URL_RE.sub(attr_callback, html)

    def srcset_callback(match: re.Match) -> str:
        items = parse_srcset(html_lib.unescape(match.group("value")))
        rewritten = [(replace_url(url), descriptor) for url, descriptor in items]
        value = srcset_value(rewritten)
        return f"{match.group('name')}{match.group('quote')}{html_lib.escape(value, quote=True)}{match.group('quote')}"

    html = SRCSET_RE.sub(srcset_callback, html)

    def style_callback(match: re.Match) -> str:
        css = rewrite_css(
            html_lib.unescape(match.group("css")),
            base_url=base,
            current_rel=current_rel,
            asset_map=asset_map,
            page_map=page_map,
        )
        return f"{match.group('prefix')}{match.group('quote')}{html_lib.escape(css, quote=True)}{match.group('quote')}"

    html = STYLE_ATTR_RE.sub(style_callback, html)

    def style_block_callback(match: re.Match) -> str:
        css = rewrite_css(
            match.group(2),
            base_url=base,
            current_rel=current_rel,
            asset_map=asset_map,
            page_map=page_map,
        )
        return f"{match.group(1)}{css}{match.group(3)}"

    html = STYLE_BLOCK_RE.sub(style_block_callback, html)
    html = BASE_RE.sub("", html)
    html = CSP_META_RE.sub("", html)
    html = INTEGRITY_ATTR_RE.sub("", html)
    if strip_scripts:
        html = SCRIPT_RE.sub("", html)
        html = SCRIPT_SELF_RE.sub("", html)
        html = EVENT_ATTR_RE.sub("", html)
    html = _force_utf8(html)
    if banner:
        html = inject_banner(html, current_rel)
    return html


def rewrite_css(
    css: str,
    *,
    base_url: str,
    current_rel: str,
    asset_map: dict[str, str],
    page_map: dict[str, str] | None = None,
) -> str:
    def replacer(match: re.Match) -> str:
        quote = match.group(1) or ""
        raw = match.group(2).strip()
        if not raw or raw.startswith(("data:", "#", "about:", "javascript:")):
            return match.group(0)
        target = _resolve_ref(
            raw,
            base_url,
            current_rel,
            page_map or {},
            asset_map,
            strip_scripts=True,
            quote_result=False,
        )
        return f"url({quote}{target}{quote})"

    from .htmlx import CSS_URL_RE

    def import_replacer(match: re.Match) -> str:
        quote = match.group(2)
        raw = match.group(3).strip()
        if not raw or raw.startswith(("data:", "#", "about:", "javascript:")):
            return match.group(0)
        target = _resolve_ref(
            raw,
            base_url,
            current_rel,
            page_map or {},
            asset_map,
            strip_scripts=True,
            quote_result=False,
        )
        return f"{match.group(1)}{quote}{target}{quote}"

    css = CSS_IMPORT_QUOTED_RE.sub(import_replacer, css)
    return CSS_URL_RE.sub(replacer, css)


def _resolve_ref(
    raw: str,
    base_url: str,
    current_rel: str,
    page_map: dict[str, str],
    asset_map: dict[str, str],
    *,
    strip_scripts: bool,
    quote_result: bool = True,
) -> str:
    value = html_lib.unescape(raw).strip()
    if not value:
        return raw
    lowered = value.lower()
    if lowered.startswith(("data:", "mailto:", "tel:", "about:", "blob:")):
        return html_lib.escape(value, quote=True) if quote_result else value
    if lowered.startswith("javascript:"):
        return "#" if strip_scripts else value
    if value.startswith("#"):
        return html_lib.escape(value, quote=True) if quote_result else value
    absolute = normalize_url(value, base_url)
    if not absolute:
        return html_lib.escape(value, quote=True) if quote_result else value
    clean, fragment = split_fragment(absolute)
    target = asset_map.get(clean) or page_map.get(clean)
    if target:
        relative = link_path(target, current_rel)
        if fragment:
            relative += "#" + urllib.parse.quote(fragment, safe="")
        result = relative
    else:
        result = absolute
        if fragment:
            result += "#" + fragment
    if quote_result:
        return html_lib.escape(result, quote=True)
    return result


def _force_utf8(html: str) -> str:
    if CHARSET_META_RE.search(html):
        html = CHARSET_META_RE.sub('<meta charset="utf-8">', html, count=1)
    else:
        if HEAD_RE.search(html):
            html = HEAD_RE.sub(r'\1<meta charset="utf-8">', html, count=1)
        else:
            meta = '<meta charset="utf-8">'
            html = meta + html
    html = CONTENT_TYPE_META_RE.sub(r'\1utf-8', html)
    return html


def inject_banner(html: str, current_rel: str) -> str:
    index_href = link_path("index.html", current_rel)
    search_href = link_path("search.html", current_rel)
    banner_html = (
        '<div id="forumkeep-bar" style="position:sticky;top:0;z-index:2147483647;'
        "background:#e7f1f2;color:#173f43;border-bottom:1px solid #b9d5d8;"
        'padding:7px 14px;font:13px/1.5 -apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'sans-serif"><strong>ForumKeep 唯讀封存</strong> · '
        f'<a style="color:#1d5b62" href="{index_href}">封存首頁</a> · '
        f'<a style="color:#1d5b62" href="{search_href}">搜尋</a>'
        "</div>"
    )
    if BODY_RE.search(html):
        return BODY_RE.sub(r"\1" + banner_html, html, count=1)
    return banner_html + html


def write_index(store: Store, site_dir: Path, pages: list, assets: list) -> None:
    counts = store.counts()
    seeds = store.seeds()
    thread_count = sum(1 for page in pages if page["kind"] == "thread")
    forum_count = sum(1 for page in pages if page["kind"] in {"forum", "index"})
    done_assets = sum(1 for asset in assets if asset["status"] == "done")
    pending_assets = sum(1 for asset in assets if asset["status"] == "pending")
    seed_lines = "".join(
        f'<li><a href="{html_lib.escape(seed)}">{html_lib.escape(seed)}</a></li>'
        for seed in seeds
    )
    recent = [page for page in pages if page["kind"] == "thread"][:30]
    recent_rows = "".join(
        f'<tr><td><a href="{link_path(page_site_path(page["url"]), "index.html")}">'
        f'{html_lib.escape(page["title"] or page["url"])}</a></td>'
        f'<td class="meta">{html_lib.escape(page["url"])}</td></tr>'
        for page in recent
    )
    body = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ForumKeep 離線封存</title>
<link rel="stylesheet" href="style.css"></head>
<body>
<header class="site"><div class="wrap"><h1>ForumKeep 離線封存</h1>
<p>只讀論壇公開素材保存 · 建置於 {html_lib.escape(utc_now())}</p>
<nav class="site"><a href="threads.html">討論串</a><a href="forums.html">版面</a>
<a href="pages.html">其他頁面</a><a href="assets.html">素材庫</a>
<a href="search.html">搜尋</a><a href="README.txt">說明</a></nav></div></header>
<main>
<div class="notice">此站是公開頁面的離線副本。文章、圖片、附件與其他檔案的著作權仍屬原作者；
請依原站授權與保存目的使用，不要任意再散布。</div>
<div class="cards">
<div class="card"><div class="num">{len(pages)}</div><div class="label">已保存頁面</div></div>
<div class="card"><div class="num">{thread_count}</div><div class="label">討論串頁面</div></div>
<div class="card"><div class="num">{forum_count}</div><div class="label">版面／首頁</div></div>
<div class="card"><div class="num">{done_assets}</div><div class="label">已下載素材</div></div>
<div class="card"><div class="num">{human_size(counts.get("asset_bytes", 0))}</div><div class="label">素材容量</div></div>
</div>
<h2>來源</h2><ul>{seed_lines}</ul>
<h2>最近的討論串</h2>
<table><thead><tr><th>標題</th><th>原始網址</th></tr></thead><tbody>{recent_rows}</tbody></table>
<p class="meta">仍有 {pending_assets} 個素材排隊中。重新執行 download 與 build 即可補齊。</p>
<h2>使用方式</h2>
<p>直接從上面的分類或搜尋頁瀏覽。封存頁面的站內連結、圖片與附件都已改寫成本機檔案；
找不到的頁面會保留原始網址，連線時仍可回到原站。</p>
</main>
<footer class="site">ForumKeep v{__version__} · SQLite 續傳 · 尊重 robots.txt 的公開保存工具</footer>
</body></html>"""
    write_text(site_dir / "index.html", body)


def write_page_listings(site_dir: Path, pages: list) -> None:
    groups = {
        "threads": ("討論串", [p for p in pages if p["kind"] == "thread"]),
        "forums": ("版面與分類", [p for p in pages if p["kind"] in {"forum", "index"}]),
        "pages": ("其他頁面", [p for p in pages if p["kind"] not in {"thread", "forum", "index"}]),
    }
    for base, (heading, items) in groups.items():
        _write_paged(
            site_dir,
            base,
            heading,
            items,
            lambda page: (
                f'<tr><td><a href="{link_path(page_site_path(page["url"]), base + ".html")}">'
                f'{html_lib.escape(page["title"] or page["url"])}</a></td>'
                f'<td class="meta">{html_lib.escape(page["url"])}</td></tr>'
            ),
            ("標題", "原始網址"),
        )


def write_asset_listing(site_dir: Path, assets: list) -> None:
    done = [asset for asset in assets if asset["status"] == "done"]

    def render(asset) -> str:
        name = html_lib.escape(asset["filename"] or asset["url"])
        rel = link_path(asset_site_path(asset), "assets.html")
        original = html_lib.escape(asset["url"])
        size = human_size(asset["size"])
        if asset["kind"] == "image":
            preview = (
                f'<a href="{rel}"><img loading="lazy" src="{rel}" alt="{name}"></a>'
            )
        else:
            preview = f'<a href="{rel}">下載</a>'
        return (
            f'<div class="asset">{preview}<div class="name">{name}</div>'
            f'<div class="meta">{html_lib.escape(asset["kind"] or "")} · {size}</div>'
            f'<div class="meta"><a href="{original}">原始網址</a></div></div>'
        )

    _write_paged(
        site_dir,
        "assets",
        "素材庫",
        done,
        render,
        (),
        grid=True,
        page_size=240,
    )


def _write_paged(
    site_dir: Path,
    base: str,
    heading: str,
    items: list,
    render,
    headers: tuple,
    *,
    grid: bool = False,
    page_size: int = 500,
) -> None:
    if not items:
        items = []
    chunks = [items[index:index + page_size] for index in range(0, len(items), page_size)] or [[]]
    for index, chunk in enumerate(chunks, start=1):
        filename = f"{base}.html" if index == 1 else f"{base}-{index}.html"
        current = filename
        if grid:
            content = '<div class="grid">' + "".join(render(item) for item in chunk) + "</div>"
        else:
            head = "".join(f"<th>{html_lib.escape(value)}</th>" for value in headers)
            rows = "".join(render(item) for item in chunk)
            content = f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"
        if not chunk:
            content = '<p class="meta">目前沒有資料。</p>'
        nav = []
        if index > 1:
            nav.append(f'<a href="{base}.html">第一頁</a>')
            nav.append(f'<a href="{base}-{index - 1}.html">上一頁</a>')
        if index < len(chunks):
            nav.append(f'<a href="{base}-{index + 1}.html">下一頁</a>')
            nav.append(f'<a href="{base}-{len(chunks)}.html">最後一頁</a>')
        page_body = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_lib.escape(heading)} · ForumKeep</title><link rel="stylesheet" href="style.css"></head>
<body><header class="site"><div class="wrap"><h1>{html_lib.escape(heading)}</h1>
<p>{len(items)} 筆 · 第 {index} / {len(chunks)} 頁</p>
<nav class="site"><a href="index.html">封存首頁</a><a href="threads.html">討論串</a>
<a href="forums.html">版面</a><a href="pages.html">其他頁面</a>
<a href="assets.html">素材庫</a><a href="search.html">搜尋</a></nav></div></header>
<main>{content}<div class="pager">{" ".join(nav)}</div></main>
<footer class="site">ForumKeep v{__version__}</footer></body></html>"""
        write_text(site_dir / filename, page_body)


def write_search(site_dir: Path, pages: list) -> None:
    index = []
    for page in pages:
        index.append({
            "t": page["title"] or page["url"],
            "u": link_path(page_site_path(page["url"]), "search.html"),
            "k": page["kind"] or "page",
            "s": (page["text"] or "")[:600],
            "o": page["url"],
        })
    script = "window.FORUMKEEP_SEARCH=" + json.dumps(index, ensure_ascii=False) + ";"
    write_text(site_dir / "search-index.js", script)
    body = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>搜尋 · ForumKeep</title><link rel="stylesheet" href="style.css"></head>
<body><header class="site"><div class="wrap"><h1>搜尋封存</h1>
<p>共 {len(index)} 頁。搜尋標題與頁面文字。</p>
<nav class="site"><a href="index.html">封存首頁</a><a href="threads.html">討論串</a>
<a href="forums.html">版面</a><a href="pages.html">其他頁面</a>
<a href="assets.html">素材庫</a></nav></div></header>
<main><input id="q" type="search" placeholder="輸入關鍵字，例如：插件、素材、教學……" autofocus>
<p class="meta" id="count"></p><div id="results"></div>
<script src="search-index.js"></script>
<script>
(function(){{
  var input=document.getElementById("q"), count=document.getElementById("count"),
      results=document.getElementById("results"), data=window.FORUMKEEP_SEARCH||[], timer=null;
  function esc(s){{return String(s).replace(/[&<>"']/g,function(c){{
    return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c];
  }});}}
  function run(){{
    var q=input.value.trim().toLowerCase();
    if(!q){{count.textContent="";results.innerHTML="";return;}}
    var hits=[];
    for(var i=0;i<data.length&&hits.length<200;i++){{
      var item=data[i], hay=(item.t+" "+item.s).toLowerCase();
      if(hay.indexOf(q)>=0) hits.push(item);
    }}
    count.textContent="找到 "+hits.length+(hits.length>=200?"+":"")+" 筆";
    results.innerHTML="<table><thead><tr><th>頁面</th><th>類型</th></tr></thead><tbody>"+hits.map(function(item){{
      return '<tr><td><a href="'+esc(item.u)+'">'+esc(item.t)+'</a><div class="meta">'+esc(item.o)+'</div></td><td>'+esc(item.k)+'</td></tr>';
    }}).join("")+"</tbody></table>";
  }}
  input.addEventListener("input",function(){{clearTimeout(timer);timer=setTimeout(run,120);}});
}})();
</script></main>
<footer class="site">ForumKeep v{__version__}</footer></body></html>"""
    write_text(site_dir / "search.html", body)


def write_manifest(store: Store, site_dir: Path, pages: list, assets: list) -> None:
    manifest = {
        "generator": f"ForumKeep {__version__}",
        "generated_at": utc_now(),
        "seeds": store.seeds(),
        "counts": store.counts(),
        "pages": [
            {
                "url": page["url"],
                "final_url": page["final_url"],
                "title": page["title"],
                "kind": page["kind"],
                "local_path": page_site_path(page["url"]),
                "sha256": page["sha256"],
                "size": page["size"],
            }
            for page in pages
        ],
        "assets": [
            {
                "url": asset["url"],
                "final_url": asset["final_url"],
                "kind": asset["kind"],
                "status": asset["status"],
                "local_path": asset_site_path(asset) if asset["status"] == "done" else None,
                "sha256": asset["sha256"],
                "size": asset["size"],
                "filename": asset["filename"],
            }
            for asset in assets
        ],
    }
    write_text(site_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


def write_site_readme(store: Store, site_dir: Path) -> None:
    counts = store.counts()
    text = f"""ForumKeep 離線論壇封存
========================

建置時間：{utc_now()}
來源：
{os.linesep.join("  - " + seed for seed in store.seeds())}

頁面：{counts.get("pages", 0)}
素材：{counts.get("assets", 0)}
素材容量：{human_size(counts.get("asset_bytes", 0))}

如何瀏覽
--------
1. 用瀏覽器開啟 index.html。
2. threads.html 是討論串列表，forums.html 是版面列表。
3. assets.html 是素材庫；search.html 可以搜尋頁面文字。
4. 頁面上方的 ForumKeep 橫幅可回到封存首頁。

保存範圍
--------
- 只保存公開頁面，不登入、不繞過權限、不對論壇送出修改請求。
- 頁面、原始 HTML、附件、圖片、文件、音訊、影片等素材放在此資料夾。
- 找不到的連結會保留原始網址，方便回到仍存在的來源。
- 頁面中的 JavaScript 與事件屬性預設已移除；原始 HTML 保留在 raw/ 目錄。

權利提醒
--------
文章、圖片、附件與其他檔案的著作權屬於原作者。本封存僅供保存與研究，
請遵守原站條款與授權，不要任意大量再散布。
"""
    write_text(site_dir / "README.txt", text)


def write_archive_readme(store: Store) -> None:
    readme = f"""ForumKeep archive
=================

SQLite: forumkeep.sqlite3
Raw HTML: raw/pages/
Asset blobs: blobs/
Offline site: site/index.html

This archive was produced by ForumKeep {__version__}.
The tool is read-only: it never logs in, posts, or bypasses access controls.
"""
    write_text(store.root / "README.txt", readme)
