from __future__ import annotations

import hashlib
import os
import posixpath
import re
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from . import __version__

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 2
DEFAULT_DELAY = 1.0
DEFAULT_PAGE_LIMIT_MB = 12.0
DEFAULT_ASSET_LIMIT_MB = 200.0
USER_AGENT = (
    f"ForumKeep/{__version__} "
    "(read-only public forum preservation; polite crawl)"
)

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "gbraid",
    "wbraid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "yclid",
    "_ga",
    "_gl",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_name",
    "utm_reader",
    "utm_social",
    "utm_social-type",
}

SESSION_PARAMS = {
    "PHPSESSID",
    "phpsessid",
    "sessionid",
    "session_id",
    "sid",
    "SID",
    "sessid",
    "sess",
}

IMAGE_EXTENSIONS = {
    ".apng", ".avif", ".bmp", ".gif", ".ico", ".jfif", ".jpeg", ".jpg",
    ".png", ".svg", ".svgz", ".tif", ".tiff", ".webp",
}
AUDIO_EXTENSIONS = {
    ".aac", ".flac", ".m4a", ".mid", ".midi", ".mp3", ".oga", ".ogg",
    ".opus", ".wav", ".wma",
}
VIDEO_EXTENSIONS = {
    ".avi", ".flv", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg",
    ".ogv", ".webm", ".wmv",
}
DOCUMENT_EXTENSIONS = {
    ".chm", ".csv", ".doc", ".docx", ".epub", ".md", ".odt", ".pdf",
    ".ppt", ".pptx", ".rtf", ".tex", ".txt", ".xls", ".xlsx",
}
ARCHIVE_EXTENSIONS = {
    ".7z", ".bz2", ".cab", ".gz", ".iso", ".rar", ".tar", ".tgz",
    ".xz", ".zip", ".zst",
}
CODE_EXTENSIONS = {
    ".c", ".cpp", ".cs", ".css", ".h", ".hpp", ".html", ".ini", ".java",
    ".js", ".json", ".lua", ".php", ".py", ".rb", ".sh", ".sql", ".toml",
    ".ts", ".xml", ".yaml", ".yml",
}
FONT_EXTENSIONS = {".eot", ".otf", ".ttf", ".woff", ".woff2"}
PAGE_EXTENSIONS = {".htm", ".html", ".xhtml", ".php", ".asp", ".aspx", ".jsp", ".cgi"}
ALL_ASSET_EXTENSIONS = (
    IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS | DOCUMENT_EXTENSIONS
    | ARCHIVE_EXTENSIONS | FONT_EXTENSIONS
)
STYLESHEET_EXTENSIONS = {".css"}
SCRIPT_EXTENSIONS = {".js", ".mjs"}

MIME_EXTENSIONS = {
    "application/atom+xml": ".xml",
    "application/epub+zip": ".epub",
    "application/gzip": ".gz",
    "application/javascript": ".js",
    "application/json": ".json",
    "application/msword": ".doc",
    "application/octet-stream": ".bin",
    "application/ogg": ".ogg",
    "application/pdf": ".pdf",
    "application/rar": ".rar",
    "application/rtf": ".rtf",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.rar": ".rar",
    "application/x-7z-compressed": ".7z",
    "application/x-bzip2": ".bz2",
    "application/x-rar-compressed": ".rar",
    "application/x-tar": ".tar",
    "application/x-zip-compressed": ".zip",
    "application/zip": ".zip",
    "audio/flac": ".flac",
    "audio/midi": ".mid",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/wav": ".wav",
    "audio/webm": ".weba",
    "font/otf": ".otf",
    "font/ttf": ".ttf",
    "font/woff": ".woff",
    "font/woff2": ".woff2",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/tiff": ".tiff",
    "image/vnd.microsoft.icon": ".ico",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
    "text/css": ".css",
    "text/csv": ".csv",
    "text/html": ".html",
    "text/javascript": ".js",
    "text/markdown": ".md",
    "text/plain": ".txt",
    "text/xml": ".xml",
    "video/mp4": ".mp4",
    "video/mpeg": ".mpeg",
    "video/ogg": ".ogv",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-flv": ".flv",
    "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi",
}

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def short_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def url_hash(url: str, length: int = 16) -> str:
    return short_hash(url, length)


def safe_filename(value: str, fallback: str = "file", max_length: int = 120) -> str:
    value = urllib.parse.unquote(value or "")
    value = value.replace("\\", "_").replace("/", "_").replace(":", "_")
    value = re.sub(r'[\x00-\x1f<>:"|?*]+', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = fallback
    stem, suffix = os.path.splitext(value)
    if stem.upper() in WINDOWS_RESERVED:
        stem = f"_{stem}"
    suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix)[:16]
    room = max(1, max_length - len(suffix))
    stem = stem[:room].rstrip(" .") or fallback
    return f"{stem}{suffix}"


def filename_from_url(url: str, fallback: str = "download") -> str:
    parts = urllib.parse.urlsplit(url)
    name = posixpath.basename(urllib.parse.unquote(parts.path.rstrip("/")))
    if not name or name in {".", ".."}:
        name = fallback
    if "." not in name:
        name = f"{name}.bin"
    return safe_filename(name, fallback=fallback)


def extension_from_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    return posixpath.splitext(path.rstrip("/"))[1].lower()


def extension_for_mime(content_type: str) -> str:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    return MIME_EXTENSIONS.get(mime, "")


def kind_for_extension(ext: str) -> str:
    ext = (ext or "").lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in ARCHIVE_EXTENSIONS:
        return "archive"
    if ext in FONT_EXTENSIONS:
        return "font"
    if ext in STYLESHEET_EXTENSIONS:
        return "stylesheet"
    if ext in SCRIPT_EXTENSIONS:
        return "script"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    if ext in CODE_EXTENSIONS:
        return "code"
    return "other"


def kind_for_url(url: str) -> str:
    return kind_for_extension(extension_from_url(url))


def kind_for_content_type(content_type: str) -> str:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime == "text/css":
        return "stylesheet"
    if "javascript" in mime:
        return "script"
    if mime.startswith("font/") or mime in {
        "application/font-woff", "application/vnd.ms-fontobject",
        "application/x-font-ttf",
    }:
        return "font"
    if mime in {
        "application/zip", "application/x-7z-compressed", "application/x-rar-compressed",
        "application/vnd.rar", "application/gzip", "application/x-tar",
    }:
        return "archive"
    if mime.startswith("text/") or mime in {
        "application/pdf", "application/json", "application/xml",
        "application/msword",
    }:
        return "document"
    return "other"


def is_http_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return parts.scheme.lower() in {"http", "https"} and bool(parts.netloc)


def origin_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else ""
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def normalize_url(url: str, base: str | None = None) -> str:
    if base:
        url = urllib.parse.urljoin(base, url)
    url = url.strip()
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.netloc:
        return ""
    host = parts.hostname.lower() if parts.hostname else ""
    if not host:
        return ""
    try:
        port = parts.port
    except ValueError:
        return ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    if parts.username or parts.password:
        return ""
    path = parts.path or "/"
    normalized_path = posixpath.normpath(path)
    if path.endswith("/") and not normalized_path.endswith("/"):
        normalized_path += "/"
    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path
    if normalized_path == "/.":
        normalized_path = "/"
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    kept = []
    for key, value in pairs:
        lowered = key.lower()
        if lowered in TRACKING_PARAMS or key in SESSION_PARAMS:
            continue
        kept.append((key, value))
    query = urllib.parse.urlencode(kept, doseq=True)
    return urllib.parse.urlunsplit((scheme, netloc, normalized_path, query, ""))


def with_fragment(url: str, fragment: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, fragment))


def split_fragment(url: str) -> tuple[str, str]:
    parts = urllib.parse.urlsplit(url)
    fragment = parts.fragment
    clean = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    return clean, fragment


def is_tracking_or_session_param(key: str) -> bool:
    return key.lower() in TRACKING_PARAMS or key in SESSION_PARAMS


def human_size(size: int | float | None) -> str:
    if size is None:
        return "-"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def atomic_write(path: str | Path, data: bytes) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    fd, temp_name = tempfile.mkstemp(prefix=".forumkeep-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def write_text(path: str | Path, text: str) -> None:
    atomic_write(path, text.encode("utf-8"))


def decode_bytes(data: bytes, content_type: str = "", head: bytes | None = None) -> tuple[str, str]:
    charset = ""
    if content_type:
        match = re.search(r"charset\s*=\s*[\"']?([A-Za-z0-9._:-]+)", content_type, re.I)
        if match:
            charset = match.group(1)
    if not charset:
        sample = (head or data[:8192]).decode("ascii", "ignore")
        match = re.search(
            r"<meta[^>]+charset\s*=\s*[\"']?\s*([A-Za-z0-9._:-]+)", sample, re.I
        )
        if not match:
            match = re.search(
                r"<meta[^>]+content\s*=\s*[\"'][^\"']*charset=([A-Za-z0-9._:-]+)",
                sample,
                re.I,
            )
        if match:
            charset = match.group(1)
    candidates = [charset] if charset else []
    candidates.extend(["utf-8", "big5", "gb18030", "shift_jis", "windows-1252", "latin-1"])
    seen = set()
    for encoding in candidates:
        encoding = encoding.strip().lower()
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return data.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace"), "utf-8"


def strip_html_text(html: str, limit: int = 500_000) -> str:
    text = re.sub(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1\s*>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    import html as html_lib

    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_content_disposition(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"filename\*\s*=\s*([^;]+)", value, re.I)
    if match:
        raw = match.group(1).strip().strip('"')
        parts = raw.split("''", 1)
        encoded = parts[1] if len(parts) == 2 else raw
        encoding = parts[0] if len(parts) == 2 else "utf-8"
        if encoding.lower() in {"utf-8", "iso-8859-1"}:
            try:
                return urllib.parse.unquote(encoded, encoding=encoding)  # type: ignore[arg-type]
            except (LookupError, UnicodeDecodeError):
                return urllib.parse.unquote(encoded)
    match = re.search(r"filename\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^;]+))", value, re.I)
    if not match:
        return ""
    name = match.group(2) or match.group(3) or match.group(4) or ""
    return urllib.parse.unquote(name.strip())


def parse_retry_after(value: str) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime

        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None
