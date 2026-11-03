from __future__ import annotations

import html as html_lib
import re
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser

from .util import kind_for_url, normalize_url

URL_ATTRS = {
    "href",
    "src",
    "poster",
    "data",
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-url",
    "background",
}
SRCSET_ATTRS = {"srcset", "data-srcset", "data-lazy-srcset"}
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
CSS_IMPORT_RE = re.compile(
    r"@import\s+(?:url\(\s*)?(['\"])(.*?)\1\s*\)?", re.I
)
META_IMAGE_KEYS = {
    "og:image",
    "og:image:url",
    "og:image:secure_url",
    "twitter:image",
    "twitter:image:src",
}
SKIP_SCHEMES = {"data", "javascript", "mailto", "tel", "blob", "about", "file", "ftp", "irc"}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


@dataclass
class Link:
    url: str
    text: str = ""
    rel: str = ""
    download: bool = False
    tag: str = "a"


@dataclass
class Resource:
    url: str
    kind: str
    tag: str = ""
    context: str = ""


@dataclass
class ParsedDocument:
    title: str = ""
    base_url: str = ""
    links: list[Link] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    text: str = ""
    has_forms: bool = False
    generator: str = ""


class _DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.base_href = ""
        self.links: list[Link] = []
        self.resources: list[Resource] = []
        self.text_parts: list[str] = []
        self.skip_depth = 0
        self.anchor_stack: list[dict] = []
        self.tag_stack: list[str] = []
        self.has_forms = False
        self.generator = ""
        self.css_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = {key.lower(): (value or "") for key, value in attrs_list}
        if tag not in VOID_TAGS:
            self.tag_stack.append(tag)
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
        elif tag == "base" and not self.base_href and attrs.get("href"):
            self.base_href = attrs["href"].strip()
        elif tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            content = attrs.get("content", "").strip()
            if key in META_IMAGE_KEYS and content:
                self._add_resource(content, "image", "meta", key)
            if key == "generator" and content:
                self.generator = content
        elif tag == "a":
            href = attrs.get("href", "").strip()
            if href:
                self.anchor_stack.append({
                    "url": href,
                    "text": [],
                    "rel": attrs.get("rel", ""),
                    "download": "download" in attrs,
                })
        elif tag == "form":
            self.has_forms = True
        elif tag in {"img", "input"}:
            self._handle_image(tag, attrs)
        elif tag in {"script", "source", "track"}:
            self._handle_source(tag, attrs)
        elif tag in {"video", "audio"}:
            if attrs.get("src"):
                self._add_resource(attrs["src"], tag, tag)
            if attrs.get("poster"):
                self._add_resource(attrs["poster"], "image", tag, "poster")
        elif tag == "embed":
            if attrs.get("src"):
                self._add_resource(attrs["src"], "video", tag)
        elif tag == "iframe" or tag == "frame":
            if attrs.get("src"):
                self._add_resource(attrs["src"], "page", tag)
        elif tag == "object":
            if attrs.get("data"):
                self._add_resource(attrs["data"], "other", tag)
        elif tag == "link":
            rel = attrs.get("rel", "").lower()
            href = attrs.get("href", "").strip()
            if href:
                if "stylesheet" in rel:
                    self._add_resource(href, "stylesheet", tag, rel)
                elif any(word in rel for word in ("icon", "preload", "manifest")):
                    self._add_resource(href, kind_for_url(href), tag, rel)
                else:
                    self._add_resource(href, "page", tag, rel)
        if tag in {"body", "table", "td", "th"} and attrs.get("background"):
            self._add_resource(attrs["background"], "image", tag, "background")
        if attrs.get("style"):
            for url in extract_css_urls(attrs["style"]):
                self._add_resource(url, kind_for_url(url), tag, "inline-style")
        for attr_name in SRCSET_ATTRS:
            if attrs.get(attr_name):
                for url, _descriptor in parse_srcset(attrs[attr_name]):
                    self._add_resource(url, "image", tag, attr_name)

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs_list)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "title":
            self.in_title = False
        elif tag == "a" and self.anchor_stack:
            anchor = self.anchor_stack.pop()
            text = " ".join("".join(anchor["text"]).split())
            self.links.append(Link(
                anchor["url"], text, anchor["rel"], anchor["download"], "a"
            ))
        if self.tag_stack:
            for index in range(len(self.tag_stack) - 1, -1, -1):
                if self.tag_stack[index] == tag:
                    del self.tag_stack[index:]
                    break

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.tag_stack and self.tag_stack[-1] == "style":
            self.css_chunks.append(data)
            for url in extract_css_urls(data):
                self._add_resource(url, kind_for_url(url), "style", "css")
        if self.anchor_stack:
            self.anchor_stack[-1]["text"].append(data)
        if self.skip_depth == 0 and data.strip():
            self.text_parts.append(data)

    def _handle_image(self, tag: str, attrs: dict[str, str]) -> None:
        alt = attrs.get("alt", "")
        for attr_name in ("src", "data-src", "data-original", "data-lazy-src", "data-url"):
            value = attrs.get(attr_name)
            if value:
                self._add_resource(value, "image", tag, alt)
        if tag == "input" and attrs.get("type", "").lower() == "image" and attrs.get("src"):
            self._add_resource(attrs["src"], "image", tag, "input-image")

    def _handle_source(self, tag: str, attrs: dict[str, str]) -> None:
        parent = ""
        for name in reversed(self.tag_stack[:-1]):
            if name in {"video", "audio", "picture"}:
                parent = name
                break
        if attrs.get("src"):
            if tag == "script":
                kind = "script"
            elif parent in {"video", "audio"}:
                kind = parent
            else:
                kind = "image"
            self._add_resource(attrs["src"], kind, tag, parent)
        if attrs.get("type") and not attrs.get("src"):
            return

    def _add_resource(self, url: str, kind: str, tag: str, context: str = "") -> None:
        url = url.strip()
        if not url or url.startswith("#"):
            return
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        if scheme in SKIP_SCHEMES:
            return
        self.resources.append(Resource(url, kind, tag, context))


def parse_html(html: str, page_url: str) -> ParsedDocument:
    parser = _DocumentParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    base = page_url
    if parser.base_href:
        resolved_base = normalize_url(parser.base_href, page_url)
        if resolved_base:
            base = resolved_base
    links: list[Link] = []
    seen_links = set()
    for link in parser.links:
        absolute = normalize_url(link.url, base)
        if not absolute:
            continue
        key = (absolute, link.text, link.rel, link.download)
        if key in seen_links:
            continue
        seen_links.add(key)
        links.append(Link(absolute, link.text, link.rel, link.download, link.tag))
    resources: list[Resource] = []
    seen_resources = set()
    for resource in parser.resources:
        absolute = normalize_url(resource.url, base)
        if not absolute:
            continue
        if absolute in seen_resources:
            continue
        seen_resources.add(absolute)
        resources.append(Resource(absolute, resource.kind, resource.tag, resource.context))
    title = " ".join("".join(parser.title_parts).split())
    text = " ".join(" ".join(parser.text_parts).split())
    return ParsedDocument(
        title=title,
        base_url=base,
        links=links,
        resources=resources,
        text=text,
        has_forms=parser.has_forms,
        generator=parser.generator,
    )


def parse_srcset(value: str) -> list[tuple[str, str]]:
    if not value:
        return []
    result: list[tuple[str, str]] = []
    index = 0
    length = len(value)
    while index < length:
        while index < length and (value[index].isspace() or value[index] == ","):
            index += 1
        if index >= length:
            break
        url_start = index
        is_data = value[index:index + 5].lower() == "data:"
        if is_data:
            while index < length and not value[index].isspace():
                index += 1
        else:
            while index < length and not value[index].isspace() and value[index] != ",":
                index += 1
        url = value[url_start:index]
        descriptor_start = index
        while index < length and value[index] != ",":
            index += 1
        descriptor = value[descriptor_start:index].strip()
        if url and not is_data:
            result.append((url, descriptor))
        if index < length and value[index] == ",":
            index += 1
    return result


def extract_css_urls(css: str) -> list[str]:
    urls: list[str] = []
    for match in CSS_URL_RE.finditer(css or ""):
        url = match.group(2).strip()
        if url and not url.lower().startswith(("data:", "#", "about:", "javascript:")):
            urls.append(url)
    for match in CSS_IMPORT_RE.finditer(css or ""):
        url = match.group(2).strip()
        if url and not url.lower().startswith(("data:", "#", "about:", "javascript:")):
            urls.append(url)
    return urls


def srcset_value(items: list[tuple[str, str]]) -> str:
    return ", ".join(f"{url} {descriptor}".strip() for url, descriptor in items)
