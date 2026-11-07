import unittest

from xfrescue.extract import extract_assets, extract_links, rewrite_html_urls, strip_scripts
from xfrescue.live import parse_live_posts, parse_page_count, parse_next_url


HTML = """
<html><head><link rel="next" href="/threads/hello.10/page-2#posts"></head>
<body>
<article class="message message--post js-post" id="js-post-100" data-author="Alice">
  <div class="message-content">
    <article class="message-body js-selectToQuote">
      <div class="bbWrapper">Hello <a href="/threads/other.20/">other</a>
        <img src="/data/attachments/1/pic.jpg">
        <a href="https://example.com/plugin.zip">plugin</a>
        <img data-src="/data/attachments/2/lazy.png">
      </div>
    </article>
  </div>
</article>
<article class="message message--post js-post" id="js-post-101" data-author="Bob">
  <div class="bbWrapper">Second</div>
</article>
</body></html>
"""


class ExtractTests(unittest.TestCase):
    def test_extract_links_and_assets(self):
        links = extract_links(HTML, "https://forums.rpgmakerweb.com/threads/hello.10/")
        urls = {link.url for link in links}
        self.assertIn("https://forums.rpgmakerweb.com/data/attachments/1/pic.jpg", urls)
        self.assertIn("https://example.com/plugin.zip", urls)
        assets, other = extract_assets(
            HTML, "https://forums.rpgmakerweb.com/threads/hello.10/"
        )
        kinds = {asset.url: asset.kind for asset in assets}
        self.assertEqual(kinds["https://forums.rpgmakerweb.com/data/attachments/1/pic.jpg"], "attachment")
        self.assertEqual(kinds["https://example.com/plugin.zip"], "archive")
        self.assertTrue(any(link.url.endswith("/threads/other.20/") for link in other))

    def test_rewrite(self):
        out = rewrite_html_urls(
            '<a href="/threads/x.1/">x</a><img src="/data/attachments/a.png">',
            lambda url: {"https://forums.rpgmakerweb.com/threads/x.1/": "x.html",
                         "https://forums.rpgmakerweb.com/data/attachments/a.png": "a.png"}.get(url),
            "https://forums.rpgmakerweb.com/threads/hello.10/",
        )
        self.assertIn('href="x.html"', out)
        self.assertIn('src="a.png"', out)

    def test_strip_scripts(self):
        out = strip_scripts('<p onclick="x()">ok</p><script>alert(1)</script>')
        self.assertNotIn("<script", out)
        self.assertNotIn("onclick", out)
        self.assertIn("ok", out)

    def test_live_post_parser(self):
        posts = parse_live_posts(HTML, "https://forums.rpgmakerweb.com/threads/hello.10/")
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["postId"], "100")
        self.assertEqual(posts[0]["authorName"], "Alice")
        self.assertIn("Hello", posts[0]["contentHtml"])
        self.assertIn("Second", posts[1]["contentHtml"])

    def test_page_count_and_next(self):
        html = '<input class="input js-pageJumpPage" max="19"><link rel="next" href="/threads/x.1/page-2">'
        self.assertEqual(parse_page_count(html), 19)
        self.assertEqual(
            parse_next_url(html, "https://forums.rpgmakerweb.com/threads/x.1/"),
            "https://forums.rpgmakerweb.com/threads/x.1/page-2",
        )


if __name__ == "__main__":
    unittest.main()
