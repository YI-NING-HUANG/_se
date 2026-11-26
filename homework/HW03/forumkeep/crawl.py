from __future__ import annotations

import re
import time
import urllib.parse
from pathlib import Path
from typing import Callable

from .htmlx import ParsedDocument, parse_html
from .net import FetchError, HttpClient, RobotsDenied
from .policy import CrawlPolicy
from .store import Store
from .util import (
    atomic_write,
    decode_bytes,
    ensure_dir,
    extension_from_url,
    human_size,
    normalize_url,
    sha256_bytes,
    strip_html_text,
    url_hash,
    utc_now,
)

H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1\s*>", re.I | re.S)


class Crawler:
    def __init__(
        self,
        store: Store,
        client: HttpClient,
        policy: CrawlPolicy,
        log: Callable[[str], None] | None = None,
        verbose: bool = False,
    ):
        self.store = store
        self.client = client
        self.policy = policy
        self.log = log or (lambda message: None)
        self.verbose = verbose

    def add_seed(self, url: str) -> str:
        normalized = normalize_url(url)
        if not normalized:
            raise ValueError(f"invalid seed URL: {url}")
        if not self.policy.allowed_hosts:
            self.policy.allowed_hosts.append(urllib.parse.urlsplit(normalized).hostname or "")
        self.store.add_seed(normalized)
        self.store.enqueue_page(
            normalized, depth=0, priority=self.policy.priority_for_page(normalized)
        )
        return normalized

    def run(
        self,
        *,
        max_pages: int | None = None,
        retry_errors: bool = False,
        force: bool = False,
    ) -> dict:
        if retry_errors:
            self.store.reset_errors()
        self.force = force
        if force:
            self.store.requeue_all_pages()
            self.store.reset_asset_errors()
        started = time.monotonic()
        fetched = 0
        skipped = 0
        errors = 0
        blocked = 0
        assets_found = 0
        seed_urls = self.store.seeds()
        if not seed_urls:
            raise RuntimeError("no seed URL configured")
        for seed in seed_urls:
            self.store.enqueue_page(
                seed, depth=0, priority=self.policy.priority_for_page(seed)
            )
        while True:
            if max_pages is not None and fetched >= max_pages:
                break
            row = self.store.next_queued_page()
            if row is None:
                break
            self.store.mark_queue_working(row["url"])
            try:
                outcome = self._process_page(row)
            except RobotsDenied as error:
                blocked += 1
                self.store.mark_queue(row["url"], "blocked", str(error))
                self.log(f"blocked by robots: {row['url']}")
                continue
            except FetchError as error:
                errors += 1
                status = "error"
                self.store.mark_queue(row["url"], status, str(error))
                self.log(f"error: {row['url']} ({error})")
                continue
            except Exception as error:
                errors += 1
                self.store.mark_queue(row["url"], "error", str(error))
                self.log(f"error: {row['url']} ({type(error).__name__}: {error})")
                continue
            if outcome["status"] == "fetched":
                fetched += 1
                assets_found += outcome["assets"]
            else:
                skipped += 1
            if fetched and fetched % 10 == 0:
                elapsed = max(0.001, time.monotonic() - started)
                self.log(
                    f"crawled {fetched} pages ({fetched / elapsed:.1f}/s), "
                    f"{assets_found} assets found, {errors} errors"
                )
        summary = {
            "fetched": fetched,
            "skipped": skipped,
            "errors": errors,
            "blocked": blocked,
            "assets_found": assets_found,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "queue": self.store.queue_counts(),
        }
        self.store.set_meta("last_crawl", summary)
        self.store.set_meta("last_crawl_at", utc_now())
        return summary

    def _process_page(self, row) -> dict:
        url = row["url"]
        depth = int(row["depth"] or 0)
        if depth > 0 and self.policy.max_depth is not None and depth > self.policy.max_depth:
            self.store.mark_queue(url, "skipped", "max depth")
            return {"status": "skipped", "assets": 0}
        existing = self.store.get_page(url)
        if (
            existing and existing["status"] == "done"
            and not self._needs_refetch(existing) and not getattr(self, "force", False)
        ):
            self.store.mark_queue(url, "done")
            return {"status": "skipped", "assets": 0}
        response = self.client.get(url)
        if response.truncated:
            raise FetchError(
                f"page exceeded size limit ({human_size(self.client.max_page_bytes)})",
                status=response.status,
                url=response.url,
            )
        if not response.is_html:
            kind = self.policy.asset_kind(url)
            self.store.enqueue_asset(
                url, page_url=url, kind=kind,
                priority=self.policy.priority_for_asset(url),
            )
            self.store.mark_queue(url, "skipped", f"non-HTML content: {response.content_type}")
            return {"status": "skipped", "assets": 1}
        html, encoding = decode_bytes(response.body, response.content_type)
        duplicate = self.store.find_page_by_final(response.url)
        if duplicate and duplicate["url"] != url and duplicate["status"] == "done":
            self.store.add_alias(url, duplicate["url"])
            self.store.add_alias(response.url, duplicate["url"])
            self.store.mark_queue(url, "done")
            return {"status": "skipped", "assets": 0}
        parsed = parse_html(html, response.url)
        title = self._h1_title(html) or parsed.title or url
        title = title.strip() or url
        next_url = self._next_url(parsed, response.url)
        page_kind = self.policy.classify_page(url, depth)
        raw_rel = Path("raw") / "pages" / f"{url_hash(url)}.html"
        raw_path = self.store.root / raw_rel
        atomic_write(raw_path, response.body)
        page = {
            "url": url,
            "final_url": response.url,
            "parent_url": row["parent_url"],
            "depth": depth,
            "kind": page_kind,
            "title": title,
            "status": "done",
            "http_status": response.status,
            "content_type": response.content_type,
            "encoding": encoding,
            "size": len(response.body),
            "sha256": sha256_bytes(response.body),
            "raw_path": raw_rel.as_posix(),
            "text": strip_html_text(html),
            "base_url": parsed.base_url,
            "next_url": next_url,
            "fetched_at": utc_now(),
            "error": None,
            "attempts": int(row["attempts"] or 0) + 1,
        }
        self.store.upsert_page(page)
        self.store.add_alias(response.url, url)
        self.store.add_alias(url, url)
        assets = self._index_links(parsed, url, depth)
        self.store.mark_queue(url, "done")
        if self.verbose:
            self.log(f"[{depth}] {title or url}")
        return {"status": "fetched", "assets": assets}

    @staticmethod
    def _needs_refetch(page) -> bool:
        if not page["raw_path"]:
            return True
        return False

    def _index_links(self, parsed: ParsedDocument, page_url: str, depth: int) -> int:
        asset_count = 0
        queued_assets: set[str] = set()
        for link in parsed.links:
            target = link.url
            if not target or target == page_url:
                continue
            internal = self.policy.host_allowed(target)
            self.store.add_link(page_url, target, link.rel, link.text, internal)
            if link.download:
                allowed = internal or self.policy.external_assets == "all"
                if allowed and not self.policy.is_excluded(target):
                    if target not in queued_assets:
                        if self.store.enqueue_asset(
                            target, page_url=page_url, kind="attachment",
                            priority=self.policy.priority_for_asset(target),
                        ):
                            asset_count += 1
                        queued_assets.add(target)
                    continue
            if internal and self.policy.page_candidate(target, depth + 1):
                self.store.enqueue_page(
                    target,
                    depth=depth + 1,
                    parent_url=page_url,
                    priority=self.policy.priority_for_page(target),
                )
                continue
            if self.policy.asset_candidate(target):
                if target in queued_assets:
                    continue
                kind = self.policy.asset_kind(target)
                if self.store.enqueue_asset(
                    target, page_url=page_url, kind=kind,
                    priority=self.policy.priority_for_asset(target),
                ):
                    asset_count += 1
                queued_assets.add(target)
        for resource in parsed.resources:
            target = resource.url
            if not target:
                continue
            if resource.kind == "page":
                internal = self.policy.host_allowed(target)
                self.store.add_link(page_url, target, resource.context, "", internal)
                if internal and self.policy.page_candidate(target, depth + 1):
                    self.store.enqueue_page(
                        target,
                        depth=depth + 1,
                        parent_url=page_url,
                        priority=self.policy.priority_for_page(target),
                    )
                continue
            if resource.kind in {"script", "iframe"}:
                continue
            if not self.policy.asset_candidate(target):
                continue
            if target in queued_assets:
                continue
            kind = resource.kind
            if kind in {"other", ""}:
                kind = self.policy.asset_kind(target)
            if self.store.enqueue_asset(
                target, page_url=page_url, kind=kind,
                priority=self.policy.priority_for_asset(target),
            ):
                asset_count += 1
            queued_assets.add(target)
        return asset_count

    @staticmethod
    def _h1_title(html: str) -> str:
        match = H1_RE.search(html or "")
        if not match:
            return ""
        return strip_html_text(match.group(1), limit=500).strip()

    @staticmethod
    def _next_url(parsed: ParsedDocument, page_url: str) -> str | None:
        for resource in parsed.resources:
            if resource.tag == "link" and "next" in resource.context.lower():
                return normalize_url(resource.url, page_url)
        for link in parsed.links:
            if "next" in link.rel.lower() or link.text.strip().lower() in {
                "next", "下一頁", "下一頁 ›", "›", "»", "next page",
            }:
                return normalize_url(link.url, page_url)
        return None


def page_site_path(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or "site"
    slug = url_hash(url, 10)
    return f"pages/{host}/{slug}.html"
