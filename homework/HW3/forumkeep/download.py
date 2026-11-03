from __future__ import annotations

import os
import tempfile
import urllib.parse
from pathlib import Path
from typing import Callable

from .htmlx import extract_css_urls
from .net import FetchError, HttpClient, RobotsDenied, TooLarge
from .policy import CrawlPolicy
from .store import Store
from .util import (
    decode_bytes,
    ensure_dir,
    extension_for_mime,
    extension_from_url,
    filename_from_url,
    kind_for_content_type,
    kind_for_extension,
    normalize_url,
    parse_content_disposition,
    safe_filename,
    sha256_bytes,
    sha256_file,
    utc_now,
)

HTML_MIME = {"text/html", "application/xhtml+xml"}


class Downloader:
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

    def run(
        self,
        *,
        kinds: set[str] | None = None,
        host: str | None = None,
        limit: int | None = None,
        retry_errors: bool = False,
        max_bytes: int = 200 * 1024 * 1024,
        dry_run: bool = False,
        mirror_css: bool = True,
    ) -> dict:
        if retry_errors:
            self.store.reset_asset_errors()
        if dry_run:
            pending = self.store.pending_assets(kinds=kinds, host=host, limit=limit)
            for asset in pending:
                self.log(f"would download [{asset['kind']}] {asset['url']}")
            return {
                "candidates": len(pending),
                "downloaded": 0,
                "failed": 0,
                "skipped": 0,
                "bytes": 0,
                "dry_run": True,
            }
        temp_dir = ensure_dir(self.store.root / "blobs" / ".tmp")
        downloaded = 0
        failed = 0
        skipped = 0
        total_bytes = 0
        attempted = 0
        visited: set[str] = set()
        while True:
            if limit is not None and attempted >= limit:
                break
            batch_limit = None if limit is None else max(0, limit - attempted)
            pending = self.store.pending_assets(
                kinds=kinds, host=host, limit=batch_limit
            )
            new_items = [asset for asset in pending if asset["url"] not in visited]
            if not new_items:
                break
            for asset in new_items:
                if limit is not None and attempted >= limit:
                    break
                url = asset["url"]
                attempted += 1
                visited.add(url)
                if self.verbose or attempted == 1 or attempted % 25 == 0:
                    self.log(f"[{attempted}] {asset['kind']}: {url}")
                fd, temp_name = tempfile.mkstemp(prefix="asset-", dir=str(temp_dir))
                os.close(fd)
                try:
                    response = self.client.download_to_file(
                        url, temp_name, max_bytes=max_bytes
                    )
                except RobotsDenied as error:
                    _safe_unlink(temp_name)
                    self.store.mark_asset_error(url, str(error), status="blocked")
                    skipped += 1
                    self.log(f"blocked by robots: {url}")
                    continue
                except TooLarge as error:
                    _safe_unlink(temp_name)
                    self.store.mark_asset_error(url, str(error), http_status=error.status)
                    failed += 1
                    self.log(f"too large: {url}")
                    continue
                except FetchError as error:
                    _safe_unlink(temp_name)
                    self.store.mark_asset_error(url, str(error), http_status=error.status)
                    failed += 1
                    self.log(f"failed: {url} ({error})")
                    continue
                except Exception as error:
                    _safe_unlink(temp_name)
                    self.store.mark_asset_error(url, f"{type(error).__name__}: {error}")
                    failed += 1
                    self.log(f"failed: {url} ({type(error).__name__}: {error})")
                    continue
                mime = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                disposition_name = parse_content_disposition(
                    response.headers.get("content-disposition", "")
                )
                url_ext = extension_from_url(url)
                mime_ext = extension_for_mime(mime)
                filename = safe_filename(
                    disposition_name or filename_from_url(url, fallback="download"),
                    fallback="download",
                )
                stem, current_ext = os.path.splitext(filename)
                if mime_ext and (
                    not current_ext
                    or current_ext.lower() in {".php", ".asp", ".aspx", ".cgi", ".bin"}
                ):
                    filename = safe_filename(f"{stem}{mime_ext}", fallback="download")
                expected_ext = os.path.splitext(filename)[1].lower() or url_ext
                if mime in HTML_MIME and expected_ext not in {".html", ".htm", ".xhtml"}:
                    _safe_unlink(temp_name)
                    self.store.mark_asset_error(
                        url,
                        f"server returned HTML instead of an asset ({mime}); "
                        "it may require login or the link may be an error page",
                        status="skipped",
                        http_status=response.status,
                    )
                    skipped += 1
                    self.log(f"skipped HTML response: {url}")
                    continue
                sha = response.sha256
                ext = os.path.splitext(filename)[1].lower()
                if not ext:
                    ext = mime_ext or extension_from_url(url) or ".bin"
                    filename = safe_filename(f"{filename}{ext}", fallback="download")
                blob_rel = Path("blobs") / sha[:2] / f"{sha}{ext}"
                blob_path = self.store.root / blob_rel
                ensure_dir(blob_path.parent)
                if blob_path.exists():
                    try:
                        existing_hash = sha256_file(blob_path)
                    except OSError:
                        existing_hash = ""
                    if existing_hash == sha:
                        _safe_unlink(temp_name)
                    else:
                        os.replace(temp_name, blob_path)
                else:
                    os.replace(temp_name, blob_path)
                kind = kind_for_content_type(mime)
                if kind in {"other", "document"} and asset["kind"] == "attachment":
                    kind = "attachment"
                if kind == "other":
                    kind = kind_for_extension(ext) or asset["kind"] or "other"
                self.store.mark_asset_done(
                    url,
                    final_url=response.url,
                    http_status=response.status,
                    content_type=response.headers.get("content-type", ""),
                    size=response.size,
                    sha256=sha,
                    filename=filename,
                    local_path=blob_rel.as_posix(),
                    kind=kind,
                )
                downloaded += 1
                total_bytes += response.size
                if mirror_css and (
                    kind == "stylesheet" or mime == "text/css" or ext == ".css"
                ):
                    self._enqueue_css_assets(blob_path, response.url)
        summary = {
            "candidates": attempted,
            "downloaded": downloaded,
            "failed": failed,
            "skipped": skipped,
            "bytes": total_bytes,
        }
        self.store.set_meta("last_download", summary)
        self.store.set_meta("last_download_at", utc_now())
        return summary

    def _enqueue_css_assets(self, path: Path, css_url: str) -> None:
        try:
            data = path.read_bytes()
            text, _encoding = decode_bytes(data, "text/css")
        except OSError:
            return
        for raw_url in extract_css_urls(text):
            target = normalize_url(raw_url, css_url)
            if not target:
                continue
            if not self.policy.asset_candidate(target):
                continue
            self.store.enqueue_asset(
                target,
                page_url=css_url,
                kind=self.policy.asset_kind(target),
                priority=self.policy.priority_for_asset(target),
                referer=css_url,
            )


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def asset_output_name(asset) -> str:
    sha = asset["sha256"] or sha256_bytes(asset["url"].encode("utf-8"))
    filename = safe_filename(asset["filename"] or filename_from_url(asset["url"]))
    ext = os.path.splitext(filename)[1]
    stem = os.path.splitext(filename)[0][:80] or "file"
    return f"{sha[:12]}-{stem}{ext}"


def parse_types(value: str | None) -> set[str] | None:
    if not value:
        return None
    result = {part.strip().lower() for part in value.split(",") if part.strip()}
    return result or None


def asset_kind_filter(value: str | None) -> set[str] | None:
    kinds = parse_types(value)
    if kinds and "all" in kinds:
        return None
    return kinds


def asset_host_from_url(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()
