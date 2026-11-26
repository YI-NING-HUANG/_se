from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forumkeep.util import (
    decode_bytes,
    extension_for_mime,
    filename_from_url,
    human_size,
    kind_for_url,
    normalize_url,
    parse_content_disposition,
    safe_filename,
    sha256_bytes,
)


class UtilTests(unittest.TestCase):
    def test_normalize_url_strips_tracking_and_fragment(self):
        url = normalize_url(
            "HTTPS://Example.COM:443/a/./b/../c/?utm_source=x&page=2&sid=123#top"
        )
        self.assertEqual(url, "https://example.com/a/c/?page=2")

    def test_normalize_url_keeps_meaningful_query(self):
        self.assertEqual(
            normalize_url("/viewtopic.php?f=2&t=9", "https://bbs.example/"),
            "https://bbs.example/viewtopic.php?f=2&t=9",
        )

    def test_normalize_url_rejects_non_http(self):
        self.assertEqual(normalize_url("javascript:alert(1)"), "")
        self.assertEqual(normalize_url("mailto:a@example.com"), "")

    def test_safe_filename_windows_reserved(self):
        self.assertEqual(safe_filename("CON.txt"), "_CON.txt")
        self.assertNotIn("?", safe_filename("a?b*c.txt"))

    def test_filename_from_attachment_url(self):
        self.assertEqual(
            filename_from_url("https://x.test/files/guide.zip?download=1"),
            "guide.zip",
        )
        self.assertEqual(
            filename_from_url("https://x.test/attachments/guide.12/"),
            "guide.12",
        )

    def test_content_disposition(self):
        self.assertEqual(
            parse_content_disposition("attachment; filename*=UTF-8''%E5%9C%96.zip"),
            "圖.zip",
        )
        self.assertEqual(
            parse_content_disposition('attachment; filename="old theme.zip"'),
            "old theme.zip",
        )

    def test_kind_and_mime_helpers(self):
        self.assertEqual(kind_for_url("https://x/a.PNG"), "image")
        self.assertEqual(kind_for_url("https://x/a.zip"), "archive")
        self.assertEqual(extension_for_mime("image/svg+xml"), ".svg")

    def test_decode_big5_meta(self):
        data = '<meta charset="big5"><p>舊論壇</p>'.encode("big5")
        text, encoding = decode_bytes(data, "text/html")
        self.assertIn("舊論壇", text)
        self.assertEqual(encoding.lower(), "big5")

    def test_human_size(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(2048), "2.0 KB")

    def test_sha256(self):
        self.assertEqual(
            sha256_bytes(b"forum"),
            "4eb41a2a9dfe70722ee4671a6d1fcc6921c26cc8bcb54e5632f5e7d740352940",
        )


if __name__ == "__main__":
    unittest.main()
