from __future__ import annotations

import hashlib
import os
import shutil
import urllib.parse
from pathlib import Path
from typing import Callable, Iterable

from .db import Store
from .net import FetchError, HttpClient, RobotsDenied
from .util import (
    content_disposition_filename,
    ensure_dir,
    filename_from_url,
    human_size,
    safe_filename,
    sha256_file,
    utc_now,
)

MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "application/x-rar-compressed": ".rar",
    "application/vnd.rar": ".rar",
    "application/x-7z-compressed": ".7z",
    "application/pdf": ".pdf",
    "application/json": ".json",
    "application/javascript": ".js",
    "text/javascript": ".js",
    "text/css": ".css",
    "text/plain": ".txt",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}


def _host_dir(host: str) -> str:
    return safe_filename(host.lower(), fallback="host")


def _url_dir(url: str) -> list[str]:
    path = urllib.parse.urlsplit(url).path
    parts = [safe_filename(p, fallback="_") for p in path.split("/") if p]
    if parts:
        parts = parts[:-1]
    return parts[:8]


def _with_extension(filename: str, content_type: str | None) -> str:
    if not content_type:
        return filename
    mime = content_type.split(";", 1)[0].strip().lower()
    ext = MIME_EXTENSIONS.get(mime)
    if not ext:
        return filename
    current = os.path.splitext(filename)[1].lower()
    if current and current != ".bin":
        return filename
    if current == ".bin":
        filename = filename[:-4]
    return filename + ext


def target_relative_path(asset, final_url: str, headers: dict[str, str],
                         sha256: str) -> Path:
    host = urllib.parse.urlsplit(final_url).netloc.lower()
    disposition = content_disposition_filename(headers.get("content-disposition"))
    filename = safe_filename(disposition or filename_from_url(final_url), fallback="file")
    filename = _with_extension(filename, headers.get("content-type"))

    if host.endswith("rpgmakerweb.com"):
        if asset["kind"] == "page_asset":
            base = Path("assets", "page", _host_dir(host))
            for part in _url_dir(final_url):
                base /= part
            return base / filename
        base = Path("assets", "forum", _host_dir(host))
        for part in _url_dir(final_url):
            base /= part
        # Keep the attachment id directory but avoid a 10k-file flat folder.
        return base / filename

    base = Path("assets", "external", _host_dir(host))
    return base / f"{sha256[:10]}-{filename}"


def _link_or_copy(blob: Path, dest: Path) -> None:
    ensure_dir(dest.parent)
    try:
        if dest.exists():
            dest.unlink()
    except OSError:
        pass
    try:
        os.link(blob, dest)
        return
    except OSError:
        pass
    shutil.copyfile(blob, dest)


class Downloader:
    def __init__(
        self,
        store: Store,
        client: HttpClient,
        root: str | Path,
        max_bytes: int = 200 * 1024 * 1024,
        log: Callable[[str], None] | None = None,
    ):
        self.store = store
        self.client = client
        self.root = Path(root)
        self.max_bytes = max_bytes
        self._log = log or (lambda msg: None)

    def run(self, kinds: Iterable[str] | None = None, limit: int | None = None,
            hosts: Iterable[str] | None = None, dry_run: bool = False,
            retry_errors: bool = False, progress_every: int = 25) -> dict:
        if retry_errors:
            reset = self.store.reset_asset_errors()
            if reset:
                self._log(f"reset {reset} failed assets to pending")
        pending = self.store.pending_assets(kinds=kinds, include_link_only=True)
        host_filter = {h.lower() for h in hosts} if hosts else None
        if host_filter:
            pending = [
                a for a in pending
                if urllib.parse.urlsplit(a["url"]).netloc.lower() in host_filter
            ]
        done = 0
        failed = 0
        skipped = 0
        blocked = 0
        bytes_done = 0
        for asset in pending:
            if limit is not None and done >= limit:
                break
            if asset["kind"] == "ignored":
                self.store.mark_asset(asset["url"], status="skipped", error="not an asset")
                skipped += 1
                continue
            if asset["status"] == "link_only":
                skipped += 1
                continue
            host = urllib.parse.urlsplit(asset["url"]).netloc.lower()
            if dry_run:
                self._log(f"would download [{asset['kind']}] {asset['url']}")
                done += 1
                continue
            try:
                result = self._download_one(asset)
            except RobotsDenied as exc:
                blocked += 1
                self._log(f"BLOCKED [{asset['kind']}] {asset['url']} :: {exc}")
                continue
            except FetchError as exc:
                self.store.mark_asset(
                    asset["url"], status="error", http_status=exc.status,
                    error=str(exc)[:500], fetched_at=utc_now(),
                )
                failed += 1
                self._log(f"FAILED [{asset['kind']}] {asset['url']} :: {exc}")
                continue
            except Exception as exc:
                self.store.mark_asset(
                    asset["url"], status="error",
                    error=f"{type(exc).__name__}: {exc}"[:500], fetched_at=utc_now(),
                )
                failed += 1
                self._log(f"FAILED [{asset['kind']}] {asset['url']} :: {exc}")
                continue
            done += 1
            bytes_done += result["size"]
            if progress_every and done % progress_every == 0:
                self._log(
                    f"downloaded {done} ({human_size(bytes_done)}), "
                    f"failed {failed}, skipped {skipped}"
                )
        return {
            "downloaded": done,
            "failed": failed,
            "skipped": skipped,
            "blocked": blocked,
            "bytes": bytes_done,
            "pending": len(pending),
        }

    def _download_one(self, asset) -> dict:
        url = asset["url"]
        if asset["kind"] == "external_file":
            # Only direct-download patterns should reach here.
            pass
        blob_dir = self.root / "blobs"
        tmp = self.root / "tmp"
        ensure_dir(tmp)
        temp_path = tmp / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".download")
        result = self.client.download(str(url), str(temp_path), max_bytes=self.max_bytes)
        sha = result.sha256
        blob_path = blob_dir / sha[:2] / sha
        ensure_dir(blob_path.parent)
        if blob_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        else:
            os.replace(temp_path, blob_path)

        local_rel = target_relative_path(asset, result.url, result.headers, sha)
        local_path = self.root / local_rel
        if local_path.exists():
            # If the same URL produced different bytes, keep both.
            try:
                existing = sha256_file(local_path)
            except OSError:
                existing = ""
            if existing and existing != sha:
                local_rel = local_rel.with_name(
                    f"{local_rel.stem}-{sha[:8]}{local_rel.suffix}"
                )
                local_path = self.root / local_rel
        _link_or_copy(blob_path, local_path)
        self.store.mark_asset(
            url,
            status="done",
            http_status=result.status,
            content_type=result.headers.get("content-type"),
            size=result.size,
            sha256=sha,
            blob_path=str(blob_path.relative_to(self.root)),
            local_path=local_rel.as_posix(),
            filename=local_rel.name,
            error=None,
            fetched_at=utc_now(),
        )
        self._log(
            f"OK [{asset['kind']}] {local_rel.as_posix()} "
            f"({human_size(result.size)})"
        )
        return {"size": result.size, "sha256": sha, "path": local_rel}

    def verify(self, fix: bool = False) -> dict:
        missing = []
        bad = []
        checked = 0
        for asset in self.store.assets(status="done"):
            checked += 1
            path = self.root / (asset["local_path"] or "")
            if not asset["local_path"] or not path.exists():
                missing.append(asset["url"])
                if fix:
                    self.store.conn.execute(
                        "UPDATE assets SET status='pending', local_path=NULL WHERE url=?",
                        (asset["url"],),
                    )
                continue
            if asset["sha256"]:
                digest = sha256_file(path)
                if digest != asset["sha256"]:
                    bad.append(asset["url"])
                    if fix:
                        self.store.conn.execute(
                            "UPDATE assets SET status='pending', local_path=NULL WHERE url=?",
                            (asset["url"],),
                        )
        if fix:
            self.store.conn.commit()
        return {"checked": checked, "missing": missing, "bad": bad}
