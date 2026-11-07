import unittest

from xfrescue.classify import classify, canonical_url


class ClassifyTests(unittest.TestCase):
    def test_forum_attachment_is_priority_zero(self):
        ref = classify("https://forums.rpgmakerweb.com/attachments/foo-png.123/")
        self.assertIsNotNone(ref)
        self.assertEqual(ref.kind, "attachment")
        self.assertEqual(ref.priority, 0)
        self.assertTrue(ref.downloadable)

    def test_forum_data_attachment(self):
        ref = classify("https://forums.rpgmakerweb.com/data/attachments/1/2-abc.jpg")
        self.assertEqual(ref.kind, "attachment")
        self.assertEqual(ref.priority, 0)

    def test_forum_thread_is_not_an_asset(self):
        ref = classify("https://forums.rpgmakerweb.com/threads/hello.123/")
        self.assertEqual(ref.kind, "forum_page")
        self.assertFalse(ref.downloadable)

    def test_direct_archive(self):
        ref = classify("https://example.com/files/plugin.zip")
        self.assertEqual(ref.kind, "archive")
        self.assertTrue(ref.downloadable)

    def test_image(self):
        ref = classify("https://example.com/pic.PNG?x=1")
        self.assertEqual(ref.kind, "image")

    def test_github_blob_becomes_raw(self):
        url = "https://github.com/u/r/blob/master/build/Plugin.js"
        self.assertEqual(
            canonical_url(url),
            "https://raw.githubusercontent.com/u/r/master/build/Plugin.js",
        )
        ref = classify(url)
        self.assertEqual(ref.kind, "code")
        self.assertEqual(ref.url, "https://raw.githubusercontent.com/u/r/master/build/Plugin.js")

    def test_file_host_page_is_link_only(self):
        ref = classify("https://itch.io/blog/1550872/some-post")
        self.assertEqual(ref.kind, "external_file")
        self.assertFalse(ref.downloadable)

    def test_mediafire_download_page_is_link_only(self):
        ref = classify("http://www.mediafire.com/download/qk995akpyaqm3sd/AKM-5.zip")
        self.assertEqual(ref.kind, "external_file")
        self.assertFalse(ref.downloadable)

    def test_mediafire_cdn_file_is_downloadable(self):
        ref = classify("https://download2392.mediafire.com/abc123/AKM-5.zip")
        self.assertEqual(ref.kind, "archive")
        self.assertTrue(ref.downloadable)

    def test_relative_url(self):
        ref = classify("/data/attachments/a.png", "https://forums.rpgmakerweb.com/threads/x.1/")
        self.assertEqual(ref.kind, "attachment")
        self.assertEqual(ref.url, "https://forums.rpgmakerweb.com/data/attachments/a.png")


if __name__ == "__main__":
    unittest.main()
