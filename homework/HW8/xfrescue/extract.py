from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from .classify import AssetRef, classify
from .util import normalize_url


@dataclass
class Link:
    url: str
    tag: str
    attr: str
    text: str = ""


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[Link] = []
        self._anchor_depth = 0
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        values = {k.lower(): (v or "") for k, v in attrs}
        if tag == "a":
            self._anchor_depth += 1
            self._anchor_text = []
        for attr in ("href", "src", "data-src", "data-original", "poster"):
            value = values.get(attr)
            if value:
                self._add(value, tag, attr)
        srcset = values.get("srcset")
        if srcset:
            for candidate in srcset.split(","):
                candidate = candidate.strip().split(" ")[0]
                if candidate:
                    self._add(candidate, tag, "srcset")
        data_media = values.get("data-media-href")
        if data_media:
            self._add(data_media, tag, "data-media-href")

    def handle_endtag(self, tag: str):
        if tag.lower() == "a" and self._anchor_depth:
            text = " ".join("".join(self._anchor_text).split())
            if text and self.links:
                for link in reversed(self.links):
                    if link.tag == "a" and not link.text:
                        link.text = text
                        break
            self._anchor_depth -= 1
            self._anchor_text = []

    def handle_data(self, data: str):
        if self._anchor_depth:
            self._anchor_text.append(data)

    def _add(self, value: str, tag: str, attr: str) -> None:
        value = html_lib.unescape(value.strip())
        if not value or value.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            return
        url = normalize_url(value, self.base_url)
        if url:
            self.links.append(Link(url=url, tag=tag, attr=attr))


def extract_links(html: str, base_url: str) -> list[Link]:
    parser = _LinkParser(base_url)
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass
    # de-duplicate preserving order
    seen = set()
    result = []
    for link in parser.links:
        key = (link.url, link.tag, link.attr)
        if key in seen:
            continue
        seen.add(key)
        result.append(link)
    return result


def extract_assets(html: str, base_url: str, page_url: str | None = None) -> tuple[list[AssetRef], list[Link]]:
    assets: list[AssetRef] = []
    other_links: list[Link] = []
    seen: set[str] = set()
    for link in extract_links(html, base_url):
        ref = classify(link.url, page_url=page_url or base_url)
        if not ref:
            continue
        if ref.url in seen:
            continue
        seen.add(ref.url)
        if ref.kind in {"forum_page", "external_link", "ignored"}:
            other_links.append(link)
        else:
            assets.append(ref)
    return assets, other_links


_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?)\s(src|data-src)\s*=\s*("|\')(.*?)\3', re.I | re.S)
_SRCSET_RE = re.compile(r'\s(srcset)\s*=\s*("|\')(.*?)\2', re.I | re.S)


def rewrite_html_urls(html: str, mapper, base_url: str) -> str:
    """Rewrite src/href attributes using mapper(url) -> new URL or None."""

    def attr_repl(match: re.Match) -> str:
        prefix, attr, quote, value = match.groups()
        url = normalize_url(html_lib.unescape(value), base_url)
        if not url:
            return match.group(0)
        new = mapper(url)
        if not new:
            return match.group(0)
        return f"{prefix} {attr}={quote}{html_lib.escape(new, quote=True)}{quote}"

    attribute_re = re.compile(r'(\b(?:href|src|poster)\s*=\s*)("|\')(.*?)\2', re.I | re.S)

    def simple_repl(match: re.Match) -> str:
        prefix, quote, value = match.groups()
        url = normalize_url(html_lib.unescape(value), base_url)
        if not url:
            return match.group(0)
        new = mapper(url)
        if not new:
            return match.group(0)
        return f"{prefix}{quote}{html_lib.escape(new, quote=True)}{quote}"

    html = attribute_re.sub(simple_repl, html or "")
    html = _IMG_SRC_RE.sub(attr_repl, html)
    html = _SRCSET_RE.sub(lambda m: "", html)
    return html


def strip_scripts(html: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html or "", flags=re.I | re.S)
    html = re.sub(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html, flags=re.I)
    html = re.sub(r"href\s*=\s*(\"|')\s*javascript:[^\"']*\1", 'href="#"', html, flags=re.I)
    return html
