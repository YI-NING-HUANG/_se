from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = (
    "xfrescue/0.1 (personal offline preservation; "
    "public pages only; contact the operator of this archive)"
)

DEFAULT_DELAY = 1.0
DEFAULT_TIMEOUT = 60
DEFAULT_RETRIES = 4


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(text: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "item"


def safe_filename(name: str, fallback: str = "file", max_len: int = 160) -> str:
    name = urllib.parse.unquote(name or "")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if not name:
        name = fallback
    if len(name) > max_len:
        stem, dot, ext = name.rpartition(".")
        if dot and 0 < len(ext) <= 12:
            keep = max_len - len(ext) - 1
            name = stem[:keep].rstrip(" .") + "." + ext
        else:
            name = name[:max_len].rstrip(" .")
    return name or fallback


def filename_from_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    name = safe_filename(path.rstrip("/").rsplit("/", 1)[-1], fallback="index")
    if "." not in name:
        name += ".bin"
    return name


def normalize_url(url: str, base: str | None = None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if base:
        url = urllib.parse.urljoin(base, url)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        return None
    if not parts.netloc:
        return None
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, "")
    )


def url_origin(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def same_host(a: str, b: str) -> bool:
    return urllib.parse.urlsplit(a).netloc.lower() == urllib.parse.urlsplit(b).netloc.lower()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    tmp = p.with_name(p.name + f".part-{os.getpid()}-{int(time.time() * 1000)}")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)


def write_text(path: str | Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def write_json(path: str | Path, obj) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def read_json(path: str | Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def human_size(num: int | float | None) -> str:
    if num is None:
        return ""
    num = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(num)} {unit}"
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def content_disposition_filename(value: str | None) -> str | None:
    if not value:
        return None
    # RFC 6266 / RFC 5987
    match = re.search(r"filename\*\s*=\s*(?:UTF-8'')?([^;]+)", value, re.I)
    if match:
        raw = match.group(1).strip().strip('"')
        try:
            return urllib.parse.unquote(raw)
        except Exception:
            return raw
    match = re.search(r'filename\s*=\s*"([^"]+)"', value, re.I)
    if match:
        return match.group(1)
    match = re.search(r"filename\s*=\s*([^;]+)", value, re.I)
    if match:
        return match.group(1).strip()
    return None


IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".bmp", ".ico",
    ".tif", ".tiff", ".jfif", ".apng",
}
ARCHIVE_EXTS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".zst",
    ".cab", ".iso",
}
CODE_EXTS = {
    ".js", ".mjs", ".cjs", ".ts", ".rb", ".json", ".xml", ".yml", ".yaml",
    ".css", ".scss", ".less", ".py", ".lua", ".cs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".sh", ".bat", ".ps1", ".txt", ".md", ".csv", ".tsv",
}
DOC_EXTS = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ppt", ".pptx", ".epub"}
AUDIO_EXTS = {".mp3", ".ogg", ".oga", ".wav", ".flac", ".m4a", ".aac", ".opus", ".mid", ".midi"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".ogv", ".wmv", ".flv"}
PAGE_EXTS = {".html", ".htm", ".xhtml", ".php", ".asp", ".aspx"}


def extension_of(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    return os.path.splitext(path.rstrip("/"))[1].lower()


def is_image_url(url: str) -> bool:
    return extension_of(url) in IMAGE_EXTS
