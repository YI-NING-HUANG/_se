from __future__ import annotations

import gzip
import json
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .util import DEFAULT_RETRIES, DEFAULT_TIMEOUT, USER_AGENT


class FetchError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status = status
        self.url = url


class RobotsDenied(FetchError):
    pass


class RateLimiter:
    def __init__(self, delay: float):
        self.delay = max(0.0, float(delay))
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def wait(self, host: str) -> None:
        if self.delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            remaining = self.delay - (now - last)
            if remaining > 0:
                time.sleep(remaining + random.uniform(0, min(0.25, self.delay * 0.1)))
                now = time.monotonic()
            self._last[host] = now


@dataclass
class Response:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass
class DownloadResult:
    url: str
    status: int
    headers: dict[str, str]
    path: str
    sha256: str
    size: int
    truncated: bool = False


class RobotsCache:
    """Small RFC-ish robots.txt matcher.

    It intentionally supports the common XenForo/WordPress shapes:
    User-agent groups, Disallow/Allow, wildcards and Crawl-delay.
    """

    def __init__(self, fetch: Callable[[str], Response], user_agent: str):
        self._fetch = fetch
        self._ua_token = re.split(r"[/\s]", user_agent.lower(), maxsplit=1)[0]
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _load(self, origin: str) -> dict:
        with self._lock:
            if origin in self._cache:
                return self._cache[origin]
        try:
            resp = self._fetch(origin.rstrip("/") + "/robots.txt")
            text = resp.body.decode("utf-8", "replace") if resp.status < 400 else ""
        except Exception:
            text = ""
        groups = self._parse(text)
        with self._lock:
            self._cache[origin] = groups
        return groups

    def _parse(self, text: str) -> dict:
        groups = []
        current = {"agents": [], "rules": [], "delay": None}
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "user-agent":
                if current["rules"] or current["agents"]:
                    groups.append(current)
                    current = {"agents": [], "rules": [], "delay": None}
                current["agents"].append(value.lower())
            elif key in ("allow", "disallow"):
                if value:
                    current["rules"].append((key, value))
            elif key == "crawl-delay":
                try:
                    current["delay"] = float(value)
                except ValueError:
                    pass
        if current["agents"] or current["rules"]:
            groups.append(current)

        selected = None
        for group in groups:
            if any(a == "*" or a in self._ua_token for a in group["agents"]):
                selected = group
                if any(a != "*" and a in self._ua_token for a in group["agents"]):
                    break
        if not selected:
            return {"rules": [], "delay": None}
        return {"rules": selected["rules"], "delay": selected["delay"]}

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        policy = self._load(origin)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        best_len = -1
        best_allow = True
        for kind, pattern in policy["rules"]:
            if self._match(pattern, path):
                plen = len(pattern)
                if plen > best_len:
                    best_len = plen
                    best_allow = kind == "allow"
        return best_allow

    @staticmethod
    def _match(pattern: str, path: str) -> bool:
        if pattern == "/":
            return path.startswith("/")
        regex = ""
        anchored = pattern.endswith("$")
        if anchored:
            pattern = pattern[:-1]
        for ch in pattern:
            if ch == "*":
                regex += ".*"
            else:
                regex += re.escape(ch)
        regex = "^" + regex + ("$" if anchored else "")
        return re.match(regex, path) is not None

    def crawl_delay(self, url: str) -> float | None:
        parts = urllib.parse.urlsplit(url)
        policy = self._load(f"{parts.scheme}://{parts.netloc}")
        return policy.get("delay")


class HttpClient:
    def __init__(
        self,
        delay: float = 1.0,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        user_agent: str = USER_AGENT,
        robots: str = "respect",
        log: Callable[[str], None] | None = None,
    ):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent
        self.robots_mode = robots
        self.limiter = RateLimiter(delay)
        self.robots = RobotsCache(self._fetch_robots, user_agent)
        self._log = log or (lambda msg: None)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }

    def _fetch_robots(self, url: str) -> Response:
        return self.get(url, check_robots=False, retries=1, allow_error=True)

    def _check_robots(self, url: str) -> None:
        if self.robots_mode == "ignore":
            return
        if self.robots.allowed(url):
            return
        if self.robots_mode == "warn":
            self._log(f"robots.txt disallows {url}; continuing because --robots=warn")
            return
        raise RobotsDenied(f"robots.txt disallows {url}", url=url)

    def get(
        self,
        url: str,
        *,
        check_robots: bool = True,
        retries: int | None = None,
        allow_error: bool = False,
        headers: dict[str, str] | None = None,
    ) -> Response:
        if check_robots:
            self._check_robots(url)
        attempts = (self.retries if retries is None else retries) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            host = urllib.parse.urlsplit(url).netloc.lower()
            self.limiter.wait(host)
            req_headers = self._headers()
            if headers:
                req_headers.update(headers)
            req = urllib.request.Request(url, headers=req_headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status = getattr(resp, "status", 200)
                    body = resp.read()
                    hdrs = {k.lower(): v for k, v in resp.headers.items()}
                    body = self._decode_transport(body, hdrs)
                    final_url = resp.geturl()
                    result = Response(final_url, status, hdrs, body)
                    if allow_error or status < 400:
                        return result
                    raise FetchError(f"HTTP {status} for {final_url}", status, final_url)
            except urllib.error.HTTPError as exc:
                status = exc.code
                try:
                    body = exc.read()
                except Exception:
                    body = b""
                hdrs = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
                body = self._decode_transport(body, hdrs)
                if allow_error:
                    return Response(url, status, hdrs, body)
                if status in (400, 401, 403, 404, 410):
                    raise FetchError(f"HTTP {status} for {url}", status, url) from exc
                last_error = FetchError(f"HTTP {status} for {url}", status, url)
                if status == 429 or 500 <= status < 600:
                    self._backoff(attempt, exc.headers.get("Retry-After") if exc.headers else None)
                    continue
                raise last_error from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = FetchError(f"network error for {url}: {exc}", url=url)
                self._backoff(attempt, None)
                continue
        assert last_error is not None
        raise last_error

    def download(
        self,
        url: str,
        dest: str,
        *,
        max_bytes: int | None = None,
        check_robots: bool = True,
        retries: int | None = None,
    ) -> DownloadResult:
        import hashlib
        import os
        from pathlib import Path

        if check_robots:
            self._check_robots(url)
        attempts = (self.retries if retries is None else retries) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            host = urllib.parse.urlsplit(url).netloc.lower()
            self.limiter.wait(host)
            req = urllib.request.Request(url, headers=self._headers())
            tmp = dest + f".part-{os.getpid()}-{attempt}"
            try:
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status = getattr(resp, "status", 200)
                    hdrs = {k.lower(): v for k, v in resp.headers.items()}
                    digest = hashlib.sha256()
                    size = 0
                    truncated = False
                    with open(tmp, "wb") as fh:
                        while True:
                            chunk = resp.read(1024 * 256)
                            if not chunk:
                                break
                            size += len(chunk)
                            if max_bytes is not None and size > max_bytes:
                                truncated = True
                                break
                            digest.update(chunk)
                            fh.write(chunk)
                        fh.flush()
                        os.fsync(fh.fileno())
                    final_url = resp.geturl()
                    if truncated:
                        try:
                            os.remove(tmp)
                        except OSError:
                            pass
                        raise FetchError(
                            f"file exceeds max size ({max_bytes} bytes): {url}",
                            status=status, url=final_url,
                        )
                    os.replace(tmp, dest)
                    return DownloadResult(
                        url=final_url,
                        status=status,
                        headers=hdrs,
                        path=dest,
                        sha256=digest.hexdigest(),
                        size=size,
                    )
            except urllib.error.HTTPError as exc:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                status = exc.code
                if status in (400, 401, 403, 404, 410):
                    raise FetchError(f"HTTP {status} for {url}", status, url) from exc
                last_error = FetchError(f"HTTP {status} for {url}", status, url)
                self._backoff(attempt, exc.headers.get("Retry-After") if exc.headers else None)
                continue
            except FetchError:
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                last_error = FetchError(f"network error for {url}: {exc}", url=url)
                self._backoff(attempt, None)
                continue
        assert last_error is not None
        raise last_error

    def get_bytes(self, url: str, **kwargs) -> bytes:
        return self.get(url, **kwargs).body

    def get_json(self, url: str, **kwargs):
        resp = self.get(url, **kwargs)
        try:
            return json.loads(resp.body.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            raise FetchError(f"invalid JSON from {url}: {exc}", url=url) from exc

    @staticmethod
    def _decode_transport(body: bytes, headers: dict[str, str]) -> bytes:
        if headers.get("content-encoding", "").lower() == "gzip" or body[:2] == b"\x1f\x8b":
            try:
                return gzip.decompress(body)
            except Exception:
                return body
        return body

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                time.sleep(min(120.0, max(0.0, float(retry_after))))
                return
            except ValueError:
                pass
        time.sleep(min(30.0, (2 ** attempt) + random.uniform(0, 1)))
