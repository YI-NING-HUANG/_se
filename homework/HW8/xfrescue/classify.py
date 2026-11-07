from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

from .util import (
    ARCHIVE_EXTS,
    AUDIO_EXTS,
    CODE_EXTS,
    DOC_EXTS,
    IMAGE_EXTS,
    PAGE_EXTS,
    VIDEO_EXTS,
    extension_of,
    normalize_url,
)

FORUM_HOST_SUFFIXES = ("rpgmakerweb.com",)
ARCHIVE_HOSTS = {"rpgmakerchat.com", "rpgmakerwiki.com"}

DIRECT_WORDS = (
    "/download/",
    "/downloads/",
    "/releases/download/",
    "/raw/",
    "/files/",
    "/file/",
)

FILE_HOST_HINTS = (
    "drive.google.com",
    "docs.google.com",
    "dropbox.com",
    "mega.nz",
    "mega.co.nz",
    "mediafire.com",
    "itch.io",
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "onedrive.live.com",
    "1drv.ms",
    "megaup.net",
    "pixeldrain.com",
    "catbox.moe",
    "files.catbox.moe",
)

PAGE_ONLY_FILE_HOSTS = {
    "mediafire.com",
    "www.mediafire.com",
}

FORUM_PAGE_RE = re.compile(
    r"^/(threads/|forums/|members/|goto/|posts/|search/|whats-new/|login/|help/|online/)",
    re.I,
)
FORUM_ASSET_RE = re.compile(r"^/(attachments/|data/attachments/)", re.I)
FORUM_STATIC_RE = re.compile(r"^/(data/avatars/|data/assets/|data/medal/|styles/|js/|css\.php|webmanifest)", re.I)

DOWNLOADABLE_KINDS = {
    "attachment",
    "image",
    "archive",
    "code",
    "document",
    "audio",
    "video",
    "page_asset",
}

KIND_LABELS = {
    "attachment": "Forum attachment",
    "image": "Image",
    "archive": "Archive",
    "code": "Code/text",
    "document": "Document",
    "audio": "Audio",
    "video": "Video",
    "page_asset": "Page asset",
    "external_file": "External file host",
    "forum_page": "Forum page",
    "external_link": "External link",
    "ignored": "Ignored",
}


@dataclass(frozen=True)
class AssetRef:
    url: str
    source_url: str
    kind: str
    priority: int
    downloadable: bool
    reason: str = ""


def canonical_url(url: str) -> str:
    """Rewrite a few common share links into direct-download equivalents."""
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path

    if host in {"github.com", "www.github.com"}:
        # https://github.com/u/r/blob/ref/path -> raw.githubusercontent.com/u/r/ref/path
        m = re.match(r"^/([^/]+)/([^/]+)/(?:blob|raw)/(.+)$", path, re.I)
        if m:
            return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"

    if host in {"www.dropbox.com", "dropbox.com"}:
        query = urllib.parse.parse_qs(parts.query)
        if "dl" in query:
            query["dl"] = ["1"]
            return urllib.parse.urlunsplit(
                (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query, doseq=True), "")
            )

    if host == "drive.google.com":
        m = re.match(r"^/file/d/([^/]+)", path)
        if m:
            return f"https://drive.google.com/uc?export=download&id={m.group(1)}"

    return url


def _kind_from_extension(url: str) -> tuple[str, int] | None:
    ext = extension_of(url)
    if ext in IMAGE_EXTS:
        return "image", 1
    if ext in ARCHIVE_EXTS:
        return "archive", 0
    if ext in CODE_EXTS:
        return "code", 0
    if ext in DOC_EXTS:
        return "document", 0
    if ext in AUDIO_EXTS:
        return "audio", 1
    if ext in VIDEO_EXTS:
        return "video", 1
    if ext in PAGE_EXTS:
        return "external_link", 9
    return None


def classify(url: str, base_url: str | None = None, page_url: str | None = None) -> AssetRef | None:
    source = normalize_url(url, base_url)
    if not source:
        return None
    canonical = canonical_url(source)
    parts = urllib.parse.urlsplit(canonical)
    host = parts.netloc.lower()
    path = parts.path or "/"
    page_host = urllib.parse.urlsplit(page_url or base_url or source).netloc.lower()

    is_forum = any(host == suffix or host.endswith("." + suffix) for suffix in FORUM_HOST_SUFFIXES)
    is_archive_host = any(host == suffix or host.endswith("." + suffix) for suffix in ARCHIVE_HOSTS)

    if is_forum:
        if FORUM_ASSET_RE.match(path):
            priority = 0 if path.startswith("/attachments/") else 0
            return AssetRef(canonical, source, "attachment", priority, True, "forum attachment")
        if FORUM_STATIC_RE.match(path):
            return AssetRef(canonical, source, "page_asset", 4, True, "forum static asset")
        if FORUM_PAGE_RE.match(path) or path in {"/", ""}:
            return AssetRef(canonical, source, "forum_page", 9, False, "forum page")
        ext_kind = _kind_from_extension(canonical)
        if ext_kind:
            kind, priority = ext_kind
            return AssetRef(canonical, source, kind, priority, True, "direct file")
        return AssetRef(canonical, source, "external_link", 9, False, "forum link")

    if is_archive_host:
        if "/api/" in path:
            return AssetRef(canonical, source, "ignored", 9, False, "archive API")
        ext_kind = _kind_from_extension(canonical)
        if ext_kind:
            kind, priority = ext_kind
            return AssetRef(canonical, source, kind, priority, True, "archive file")
        return AssetRef(canonical, source, "external_link", 9, False, "archive page")

    if host in PAGE_ONLY_FILE_HOSTS:
        return AssetRef(canonical, source, "external_file", 2, False, "file host page (bookmark only)")

    ext_kind = _kind_from_extension(canonical)
    if ext_kind:
        kind, priority = ext_kind
        if kind == "external_link":
            return AssetRef(canonical, source, "external_link", 9, False, "web page")
        return AssetRef(canonical, source, kind, priority, True, "direct file")

    if any(host == h or host.endswith("." + h) for h in FILE_HOST_HINTS):
        if any(word in path.lower() for word in DIRECT_WORDS):
            return AssetRef(canonical, source, "external_file", 2, True, "file host direct path")
        return AssetRef(canonical, source, "external_file", 2, False, "file host page (bookmark only)")

    if host != page_host and path.count("/") >= 2:
        return AssetRef(canonical, source, "external_link", 9, False, "web page")

    return AssetRef(canonical, source, "external_link", 9, False, "web page")
