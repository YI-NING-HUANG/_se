from __future__ import annotations

import unittest

from forumkeep.htmlx import extract_css_urls, parse_html, parse_srcset


BASE = "https://forum.example/threads/demo.html"


class HtmlTests(unittest.TestCase):
    def test_extracts_links_resources_and_text(self):
        html = """
        <html><head>
          <base href="/threads/">
          <title>Demo Thread</title>
          <link rel="stylesheet" href="/style.css">
          <meta property="og:image" content="/images/og.png">
        </head><body>
          <a href="other.html">Other Page</a>
          <a href="/files/pack.zip" download>Pack</a>
          <img src="/images/a.png" srcset="/images/a.png 1x, /images/a@2x.png 2x" alt="A">
          <video poster="/images/poster.jpg"><source src="/media/clip.mp4"></video>
          <div style="background:url('/images/bg.png')">x</div>
          <style>body{background:url(/images/style-bg.png)}</style>
          <script src="/app.js"></script>
          <p>Hello forum</p>
        </body></html>
        """
        doc = parse_html(html, BASE)
        self.assertEqual(doc.title, "Demo Thread")
        self.assertIn("Hello forum", doc.text)
        self.assertEqual(doc.base_url, "https://forum.example/threads/")
        urls = {link.url for link in doc.links}
        self.assertIn("https://forum.example/threads/other.html", urls)
        self.assertIn("https://forum.example/files/pack.zip", urls)
        download = [link for link in doc.links if "pack.zip" in link.url][0]
        self.assertTrue(download.download)
        resources = {resource.url for resource in doc.resources}
        self.assertIn("https://forum.example/style.css", resources)
        self.assertIn("https://forum.example/images/a@2x.png", resources)
        self.assertIn("https://forum.example/images/poster.jpg", resources)
        self.assertIn("https://forum.example/media/clip.mp4", resources)
        self.assertIn("https://forum.example/images/bg.png", resources)
        self.assertIn("https://forum.example/images/style-bg.png", resources)
        self.assertIn("https://forum.example/app.js", resources)
        self.assertIn("https://forum.example/images/og.png", resources)

    def test_srcset_parser(self):
        items = parse_srcset("a.png 1x, b.png 2x, data:image/png;base64,xxx 3x")
        self.assertEqual(items, [("a.png", "1x"), ("b.png", "2x")])

    def test_css_urls(self):
        css = """
        @import "base.css";
        body { background: url('../img/a.png'); }
        .x { src: url(data:image/png;base64,xxx); }
        """
        urls = extract_css_urls(css)
        self.assertIn("base.css", urls)
        self.assertIn("../img/a.png", urls)
        self.assertNotIn("data:image/png;base64,xxx", urls)


if __name__ == "__main__":
    unittest.main()
