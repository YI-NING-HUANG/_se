from __future__ import annotations

import io
import zipfile

from .mock_server import Route, html

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect width="10" height="10" fill="#336699"/></svg>'
)


def zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("readme.txt", "sample guide\n")
        archive.writestr("data.txt", "x" * 200)
    return buffer.getvalue()


def forum_routes() -> dict[str, Route]:
    pages = {
        "/robots.txt": Route(
            b"User-agent: *\nAllow: /\nDisallow: /private/\nCrawl-delay: 0\n",
            content_type="text/plain; charset=utf-8",
        ),
        "/": html("""
            <html><head><title>Forum Home</title></head><body>
            <a href="/forum.html">Help Forum</a>
            <a href="/threads/one.html">One</a>
            <a href="/files/guide.zip">Guide archive</a>
            <a href="/private/secret.html">Private</a>
            <a href="/redirect">Redirect</a>
            </body></html>
        """),
        "/forum.html": html("""
            <html><head><title>Help Forum</title></head><body>
            <h1>Help Forum</h1>
            <a href="/threads/one.html">One</a>
            <a href="/threads/two.html">Two</a>
            <a href="/download.php?id=7">Download seven</a>
            </body></html>
        """),
        "/threads/one.html": html("""
            <html><head><title>One - Help Forum</title>
            <link rel="stylesheet" href="/style.css">
            <link rel="next" href="/threads/one.html?page=2">
            <script>alert('inline')</script>
            <script src="/app.js"></script>
            </head><body onload="alert('event')">
            <h1>One Thread</h1>
            <article class="post"><p>First post 舊文章</p>
            <img src="/images/pic.svg" srcset="/images/pic.svg 1x, /images/pic@2x.svg 2x" alt="pic">
            <p><a class="attachment" href="/attachments/guide.12/">the guide</a></p>
            <p><a href="/threads/two.html">Two</a></p>
            </article>
            <div style="background:url('/images/pic.svg')">styled</div>
            </body></html>
        """),
        "/threads/one.html?page=2": html("""
            <html><head><title>One - Page 2</title>
            <link rel="stylesheet" href="/style.css"></head>
            <body><h1>One Thread page 2</h1><article><p>Second page</p></article></body></html>
        """),
        "/threads/two.html": html("""
            <html><head><title>Two - Help Forum</title>
            <link rel="stylesheet" href="/style.css"></head>
            <body><h1>Two Thread</h1>
            <article><p>Another thread</p><img src="/images/bg.svg"></article>
            </body></html>
        """),
        "/private/secret.html": html("<html><body>secret</body></html>"),
        "/redirect": Route(b"", status=302, headers={"Location": "/forum.html"}),
        "/attachments/guide.12/": Route(
            b"the guide contents\n",
            content_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="the-guide.txt"'},
        ),
        "/download.php?id=7": Route(
            b"download id seven\n",
            content_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="seven.txt"'},
        ),
        "/files/guide.zip": Route(zip_bytes(), content_type="application/zip"),
        "/style.css": Route(
            b'@import "nested.css";\nbody{background:url("/images/bg.svg")}\n',
            content_type="text/css; charset=utf-8",
        ),
        "/nested.css": Route(
            b'.x{background:url("/images/pic.svg")}\n',
            content_type="text/css; charset=utf-8",
        ),
        "/app.js": Route(b"console.log('x');", content_type="text/javascript"),
        "/images/pic.svg": Route(SVG.encode("utf-8"), content_type="image/svg+xml"),
        "/images/pic@2x.svg": Route(SVG.encode("utf-8"), content_type="image/svg+xml"),
        "/images/bg.svg": Route(SVG.encode("utf-8"), content_type="image/svg+xml"),
    }
    return pages
