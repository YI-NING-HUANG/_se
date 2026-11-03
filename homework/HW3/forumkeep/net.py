from __future__ import annotations

import gzip
import hashlib
import os
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from typing import Callable

from .util import (
    DEFAULT_DELAY,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    USER_AGENT,
    host_of,
    origin_of,
    parse_retry_after,
)
from . import __version__


class FetchError(RuntimeError):
    def __init__(
        self,
        message: str,
        status: int | None = None,
        url: str | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status = status
        self.url = url
        self.retryable = retryable


class RobotsDenied(FetchError):
    pass


class TooLarge(FetchError):
    pass



@dataclass
class FileResponse:
    url: str
    status: int
    headers: dict[str, str]
    path: str
    size: int
    sha256: str


@dataclass
class Response:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    truncated: bool = False

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    @property
    def is_html(self) -> bool:
        mime = self.content_type.split(";", 1)[0].strip().lower()
        if mime in {"text/html", "application/xhtml+xml"}:
            return True
        if not mime and self.body.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
            return True
        return False


class RateLimiter:
    def __init__(self, delay: float = DEFAULT_DELAY):
        self.delay = max(0.0, float(delay))
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def wait(self, host: str, extra: float = 0.0) -> None:
        delay = max(self.delay, extra)
        if delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            remaining = delay - (now - last)
            if remaining > 0:
                time.sleep(remaining + random.uniform(0, min(0.2, delay * 0.05)))
                now = time.monotonic()
            self._last[host] = now


class RobotsPolicy:
    def __init__(self, text: str = "", user_agent: str = USER_AGENT):
        token = re.split(r"[/\s]", user_agent.lower(), maxsplit=1)[0]
        self.user_agent_token = token or "forumkeep"
        self.rules: list[tuple[str, str]] = []
        self.crawl_delay_value: float | None = None
        self.sitemaps: list[str] = []
        self._parse(text or "")

    def _parse(self, text: str) -> None:
        groups: list[dict] = []
        current = {"agents": [], "rules": [], "delay": None}
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "user-agent":
                if current["agents"] and (current["rules"] or current["delay"] is not None):
                    groups.append(current)
                    current = {"agents": [], "rules": [], "delay": None}
                elif current["rules"] and current["agents"]:
                    groups.append(current)
                    current = {"agents": [], "rules": [], "delay": None}
                current["agents"].append(value.lower())
            elif key in {"allow", "disallow"}:
                if value:
                    current["rules"].append((key, value))
            elif key == "crawl-delay":
                try:
                    current["delay"] = max(0.0, float(value))
                except ValueError:
                    pass
            elif key == "sitemap" and value:
                self.sitemaps.append(value)
        if current["agents"] or current["rules"]:
            groups.append(current)

        exact: list[dict] = []
        wildcard: list[dict] = []
        for group in groups:
            agents = group["agents"]
            if any(agent != "*" and agent and agent in self.user_agent_token for agent in agents):
                exact.append(group)
            elif "*" in agents:
                wildcard.append(group)
        selected = exact or wildcard
        for group in selected:
            self.rules.extend(group["rules"])
            if group["delay"] is not None:
                self.crawl_delay_value = max(
                    self.crawl_delay_value or 0.0, group["delay"]
                )

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        best_length = -1
        best_allowed = True
        for kind, pattern in self.rules:
            if _robots_match(pattern, path):
                length = len(pattern)
                if length > best_length:
                    best_length = length
                    best_allowed = kind == "allow"
                elif length == best_length and kind == "allow":
                    best_allowed = True
        return best_allowed

    @property
    def crawl_delay(self) -> float | None:
        return self.crawl_delay_value


def _robots_match(pattern: str, path: str) -> bool:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    regex = ""
    for char in pattern:
        if char == "*":
            regex += ".*"
        else:
            regex += re.escape(char)
    if anchored:
        regex += "$"
    if not regex.startswith("/"):
        regex = "/" + regex
    return re.match(regex, path) is not None


class RobotsCache:
    def __init__(self, client: "HttpClient", user_agent: str):
        self.client = client
        self.user_agent = user_agent
        self._cache: dict[str, RobotsPolicy] = {}
        self._lock = threading.Lock()

    def get(self, url: str) -> RobotsPolicy:
        origin = origin_of(url)
        with self._lock:
            if origin in self._cache:
                return self._cache[origin]
        try:
            response = self.client._open(
                origin + "/robots.txt",
                check_robots=False,
                retries=0,
                timeout_override=15.0,
            )
            text = response.body.decode("utf-8", "replace") if response.status < 400 else ""
        except Exception:
            text = ""
        policy = RobotsPolicy(text, self.user_agent)
        with self._lock:
            self._cache[origin] = policy
        return policy


class HttpClient:
    def __init__(
        self,
        *,
        delay: float = DEFAULT_DELAY,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        user_agent: str = USER_AGENT,
        robots: str = "respect",
        max_page_bytes: int = 12 * 1024 * 1024,
        log: Callable[[str], None] | None = None,
    ):
        if robots not in {"respect", "warn", "ignore"}:
            raise ValueError("robots must be respect, warn, or ignore")
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.retries = max(0, retries)
        self.user_agent = user_agent
        self.robots_mode = robots
        self.max_page_bytes = max_page_bytes
        self.limiter = RateLimiter(delay)
        self._log = log or (lambda message: None)
        self.robots_cache = RobotsCache(self, user_agent)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close",
        }

    def _check_robots(self, url: str) -> RobotsPolicy:
        if self.robots_mode == "ignore":
            return RobotsPolicy("", self.user_agent)
        policy = self.robots_cache.get(url)
        if policy.allowed(url):
            return policy
        if self.robots_mode == "warn":
            self._log(f"robots.txt disallows {url}; continuing because robots=warn")
            return policy
        raise RobotsDenied(f"robots.txt disallows {url}", url=url)

    def get(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
        allow_error: bool = False,
        check_robots: bool = True,
        headers: dict[str, str] | None = None,
    ) -> Response:
        response = self._open(
            url,
            check_robots=check_robots,
            allow_error=allow_error,
            headers=headers,
            max_bytes=max_bytes if max_bytes is not None else self.max_page_bytes,
        )
        return response

    def _open(
        self,
        url: str,
        *,
        check_robots: bool,
        retries: int | None = None,
        allow_error: bool = False,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
        timeout_override: float | None = None,
    ) -> Response:
        policy = self._check_robots(url) if check_robots else None
        crawl_delay = policy.crawl_delay if policy and policy.crawl_delay else 0.0
        host = host_of(url)
        attempts = self.retries if retries is None else max(0, retries)
        last_error: Exception | None = None
        for attempt in range(attempts + 1):
            self.limiter.wait(host, crawl_delay)
            request_headers = self._headers()
            if headers:
                request_headers.update(headers)
            request = urllib.request.Request(url, headers=request_headers, method="GET")
            try:
                with urllib.request.urlopen(
                    request, timeout=timeout_override or self.timeout
                ) as raw:
                    final_url = raw.geturl()
                    if check_robots and final_url != url:
                        final_policy = self._check_robots(final_url)
                        if final_policy.crawl_delay:
                            self.limiter.wait(host_of(final_url), final_policy.crawl_delay)
                    status = getattr(raw, "status", 200) or 200
                    response_headers = {
                        key.lower(): value for key, value in raw.headers.items()
                    }
                    content_length = response_headers.get("content-length")
                    if (
                        max_bytes is not None
                        and content_length
                        and content_length.isdigit()
                        and int(content_length) > max_bytes
                    ):
                        raise TooLarge(
                            f"response is larger than {max_bytes} bytes: {final_url}",
                            status=status,
                            url=final_url,
                        )
                    buffer = bytearray()
                    truncated = False
                    while True:
                        chunk = raw.read(64 * 1024)
                        if not chunk:
                            break
                        buffer.extend(chunk)
                        if max_bytes is not None and len(buffer) > max_bytes:
                            truncated = True
                            break
                    body = _decode_transport(bytes(buffer), response_headers)
                    response = Response(final_url, status, response_headers, body, truncated)
                    if allow_error or 200 <= status < 300:
                        return response
                    raise FetchError(
                        f"HTTP {status} for {final_url}",
                        status=status,
                        url=final_url,
                        retryable=status in {408, 425, 429} or status >= 500,
                    )
            except TooLarge:
                raise
            except RobotsDenied:
                raise
            except urllib.error.HTTPError as error:
                status = error.code
                retry_after = parse_retry_after(error.headers.get("Retry-After", ""))
                if allow_error:
                    body = error.read()
                    response_headers = {
                        key.lower(): value for key, value in error.headers.items()
                    }
                    return Response(
                        error.geturl() or url, status, response_headers,
                        _decode_transport(body, response_headers),
                    )
                if attempt < attempts and (
                    status in {408, 425, 429, 500, 502, 503, 504}
                ):
                    self._backoff(attempt, retry_after)
                    last_error = error
                    continue
                raise FetchError(
                    f"HTTP {status} for {url}",
                    status=status,
                    url=url,
                    retryable=status in {408, 425, 429} or status >= 500,
                ) from error
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
                last_error = error
                if attempt < attempts:
                    self._backoff(attempt, None)
                    continue
                reason = getattr(error, "reason", None) or error
                raise FetchError(
                    f"request failed for {url}: {reason}",
                    url=url,
                    retryable=True,
                ) from error
        raise FetchError(
            f"request failed for {url}: {last_error}",
            url=url,
            retryable=True,
        )


    def download_to_file(
        self,
        url: str,
        path: str,
        *,
        max_bytes: int,
        headers: dict[str, str] | None = None,
    ) -> FileResponse:
        policy = self._check_robots(url)
        crawl_delay = policy.crawl_delay if policy.crawl_delay else 0.0
        host = host_of(url)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self.limiter.wait(host, crawl_delay)
            request_headers = self._headers()
            request_headers["Accept-Encoding"] = "identity"
            if headers:
                request_headers.update(headers)
            request = urllib.request.Request(url, headers=request_headers, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as raw:
                    final_url = raw.geturl()
                    if final_url != url:
                        final_policy = self._check_robots(final_url)
                        if final_policy.crawl_delay:
                            self.limiter.wait(host_of(final_url), final_policy.crawl_delay)
                    status = getattr(raw, "status", 200) or 200
                    response_headers = {
                        key.lower(): value for key, value in raw.headers.items()
                    }
                    content_length = response_headers.get("content-length")
                    if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                        raise TooLarge(
                            f"file is larger than {max_bytes} bytes: {final_url}",
                            status=status,
                            url=final_url,
                        )
                    digest = hashlib.sha256()
                    size = 0
                    with open(path, "wb") as handle:
                        while True:
                            chunk = raw.read(128 * 1024)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > max_bytes:
                                raise TooLarge(
                                    f"file is larger than {max_bytes} bytes: {final_url}",
                                    status=status,
                                    url=final_url,
                                )
                            digest.update(chunk)
                            handle.write(chunk)
                        handle.flush()
                        os.fsync(handle.fileno())
                    return FileResponse(
                        final_url, status, response_headers, path, size, digest.hexdigest()
                    )
            except TooLarge:
                _safe_unlink(path)
                raise
            except RobotsDenied:
                _safe_unlink(path)
                raise
            except urllib.error.HTTPError as error:
                _safe_unlink(path)
                status = error.code
                retry_after = parse_retry_after(error.headers.get("Retry-After", ""))
                if attempt < self.retries and (
                    status in {408, 425, 429, 500, 502, 503, 504}
                ):
                    self._backoff(attempt, retry_after)
                    last_error = error
                    continue
                raise FetchError(
                    f"HTTP {status} for {url}",
                    status=status,
                    url=url,
                    retryable=status in {408, 425, 429} or status >= 500,
                ) from error
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
                _safe_unlink(path)
                last_error = error
                if attempt < self.retries:
                    self._backoff(attempt, None)
                    continue
                reason = getattr(error, "reason", None) or error
                raise FetchError(
                    f"download failed for {url}: {reason}",
                    url=url,
                    retryable=True,
                ) from error
        _safe_unlink(path)
        raise FetchError(
            f"download failed for {url}: {last_error}",
            url=url,
            retryable=True,
        )

    def _backoff(self, attempt: int, retry_after: float | None) -> None:
        wait = retry_after if retry_after is not None else min(30.0, 1.5 * (2 ** attempt))
        wait += random.uniform(0, 0.4)
        self._log(f"retrying in {wait:.1f}s")
        time.sleep(wait)


def _decode_transport(data: bytes, headers: dict[str, str]) -> bytes:
    encoding = headers.get("content-encoding", "").lower()
    if not data or not encoding:
        return data
    try:
        if "gzip" in encoding:
            return gzip.decompress(data)
        if "deflate" in encoding:
            try:
                return zlib.decompress(data)
            except zlib.error:
                return zlib.decompress(data, -zlib.MAX_WBITS)
    except (OSError, zlib.error):
        return data
    return data


def version_string() -> str:
    return f"ForumKeep {__version__}"


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
