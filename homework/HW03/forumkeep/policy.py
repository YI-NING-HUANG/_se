from __future__ import annotations

import fnmatch
import re
import urllib.parse
from dataclasses import dataclass, field

from .util import (
    ALL_ASSET_EXTENSIONS,
    PAGE_EXTENSIONS,
    STYLESHEET_EXTENSIONS,
    host_of,
    is_http_url,
    kind_for_url,
    normalize_url,
)

DEFAULT_EXCLUDES = (
    "*/login*",
    "*/log-in*",
    "*/logout*",
    "*/log-out*",
    "*/register*",
    "*/signup*",
    "*/sign-up*",
    "*/lost-password*",
    "*/forgot*",
    "*/password*",
    "*/search*",
    "*/admin*",
    "*/modcp*",
    "*/report*",
    "*/reply*",
    "*/quote*",
    "*/edit*",
    "*/delete*",
    "*/posting.php*",
    "*/ucp.php*",
    "*/misc.php?action=*",
    "*/ajax*",
    "*/cron*",
    "*/mark-read*",
    "*/markread*",
)

ACTION_QUERY_RE = re.compile(
    r"(?:^|&)(?:do|action|mode|app)=(?:login|logout|register|signup|lostpass|lost-password|"
    r"lost_password|search|reply|quote|edit|delete|report|markread|mark-read|unread)(?:&|$)",
    re.I,
)

ASSET_PATH_HINTS = (
    "/attachment",
    "/attachments/",
    "/download",
    "/downloads/",
    "/files/",
    "/file/",
    "/uploads/",
    "/upload/",
    "/media/",
    "/storage/",
    "/images/",
    "/image/",
    "/img/",
    "/fonts/",
    "/font/",
    "/avatars/",
    "/avatar/",
    "/assets/",
    "/static/",
    "/cdn/",
    "/getfile",
    "/getattachment",
)

THREAD_HINTS = (
    "/threads/",
    "/thread/",
    "/topic/",
    "/topics/",
    "/t/",
    "/viewtopic",
    "/showthread",
    "/viewthread",
    "/forum.php?mod=viewthread",
    "/thread-",
    "/posts/",
)

FORUM_HINTS = (
    "/forum/",
    "/forums/",
    "/board/",
    "/boards/",
    "/category/",
    "/categories/",
    "/c/",
    "/f/",
    "/viewforum",
    "/forumdisplay",
    "/forum-",
    "/index.php?board",
    "/index.php?action=forum",
)


def _pattern_matches(pattern: str, url: str) -> bool:
    path = urllib.parse.urlsplit(url).path or "/"
    return fnmatch.fnmatch(url, pattern) or fnmatch.fnmatch(path, pattern)


def _host_matches(host: str, pattern: str) -> bool:
    pattern = pattern.lower().strip()
    if not pattern:
        return False
    if pattern.startswith("*."):
        base = pattern[2:]
        return host == base or host.endswith("." + base)
    return host == pattern


@dataclass
class CrawlPolicy:
    seeds: list[str] = field(default_factory=list)
    allowed_hosts: list[str] = field(default_factory=list)
    path_prefixes: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    external_assets: str = "same-host"
    max_depth: int | None = None
    use_default_excludes: bool = True

    def __post_init__(self) -> None:
        self.seeds = [normalize_url(seed) for seed in self.seeds if normalize_url(seed)]
        if not self.allowed_hosts:
            self.allowed_hosts = sorted({host_of(seed) for seed in self.seeds if host_of(seed)})
        self.allowed_hosts = [host.lower().strip() for host in self.allowed_hosts if host.strip()]
        self.exclude_patterns = [p for p in self.exclude_patterns if p]
        if self.use_default_excludes:
            self.exclude_patterns = list(DEFAULT_EXCLUDES) + self.exclude_patterns
        self.path_prefixes = [p if p.startswith("/") else "/" + p for p in self.path_prefixes if p]

    def host_allowed(self, url: str) -> bool:
        host = host_of(url)
        return any(_host_matches(host, pattern) for pattern in self.allowed_hosts)

    def path_allowed(self, url: str) -> bool:
        if not self.path_prefixes:
            return True
        path = urllib.parse.urlsplit(url).path or "/"
        return any(path.startswith(prefix) for prefix in self.path_prefixes)

    def is_excluded(self, url: str) -> bool:
        if not is_http_url(url):
            return True
        parts = urllib.parse.urlsplit(url)
        if ACTION_QUERY_RE.search(parts.query or ""):
            return True
        return any(_pattern_matches(pattern, url) for pattern in self.exclude_patterns)

    def page_candidate(self, url: str, depth: int) -> bool:
        url = normalize_url(url)
        if not url or not self.host_allowed(url) or not self.path_allowed(url):
            return False
        if self.max_depth is not None and depth > self.max_depth:
            return False
        if self.is_excluded(url):
            return False
        if self.include_patterns and not any(
            _pattern_matches(pattern, url) for pattern in self.include_patterns
        ):
            return False
        if self.looks_like_asset(url):
            return False
        ext = _extension(url)
        if ext in ALL_ASSET_EXTENSIONS or ext in STYLESHEET_EXTENSIONS:
            return False
        combined = (
            urllib.parse.urlsplit(url).path + "?" + urllib.parse.urlsplit(url).query
        ).lower()
        known_forum_page = any(
            hint in combined for hint in THREAD_HINTS + FORUM_HINTS
        )
        if ext and ext not in PAGE_EXTENSIONS and not _looks_like_download_route(url) and not known_forum_page:
            return False
        return True

    def asset_candidate(self, url: str) -> bool:
        url = normalize_url(url)
        if not url:
            return False
        if self.is_excluded(url):
            return False
        same_site = self.host_allowed(url)
        if not same_site:
            if self.external_assets == "none":
                return False
            if self.external_assets == "same-host":
                return False
        if not self.path_allowed(url) and same_site:
            return False
        return self.looks_like_asset(url)

    def looks_like_asset(self, url: str) -> bool:
        ext = _extension(url)
        if ext in ALL_ASSET_EXTENSIONS or ext in STYLESHEET_EXTENSIONS:
            return True
        path_query = (urllib.parse.urlsplit(url).path + "?" + urllib.parse.urlsplit(url).query).lower()
        return any(hint in path_query for hint in ASSET_PATH_HINTS)

    def classify_page(self, url: str, depth: int = 0) -> str:
        path = urllib.parse.urlsplit(url).path.lower()
        query = urllib.parse.urlsplit(url).query.lower()
        combined = path + "?" + query
        if depth == 0 and path in {"", "/"}:
            return "index"
        if any(hint in combined for hint in THREAD_HINTS):
            return "thread"
        if any(hint in combined for hint in FORUM_HINTS):
            return "forum"
        return "page"

    def priority_for_page(self, url: str) -> int:
        kind = self.classify_page(url)
        if kind == "thread":
            return 0
        if kind in {"forum", "index"}:
            return 1
        return 2

    def priority_for_asset(self, url: str) -> int:
        kind = self.asset_kind(url)
        return {
            "attachment": 0,
            "archive": 1,
            "document": 2,
            "image": 3,
            "audio": 4,
            "video": 5,
            "stylesheet": 6,
            "font": 7,
        }.get(kind, 8)

    def asset_kind(self, url: str) -> str:
        path = urllib.parse.urlsplit(url).path.lower()
        if any(hint in path for hint in ("/attachment", "/getattachment", "/getfile")):
            return "attachment"
        kind = kind_for_url(url)
        if kind == "other" and any(hint in path for hint in ("/download", "/files/", "/uploads/")):
            return "attachment"
        return kind


def _extension(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def _looks_like_download_route(url: str) -> bool:
    combined = (urllib.parse.urlsplit(url).path + "?" + urllib.parse.urlsplit(url).query).lower()
    return any(
        hint in combined
        for hint in ("attachment", "download", "getfile", "act=attach", "act=down")
    )
