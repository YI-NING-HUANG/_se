from __future__ import annotations

import unittest

from forumkeep.policy import CrawlPolicy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = CrawlPolicy(
            seeds=["https://forum.example/"],
            external_assets="same-host",
        )

    def test_page_candidates(self):
        self.assertTrue(self.policy.page_candidate("https://forum.example/", 0))
        self.assertTrue(
            self.policy.page_candidate("https://forum.example/threads/abc.123/", 1)
        )
        self.assertTrue(
            self.policy.page_candidate("https://forum.example/viewtopic.php?t=9", 1)
        )

    def test_assets_and_external(self):
        self.assertTrue(
            self.policy.asset_candidate("https://forum.example/files/pack.zip")
        )
        self.assertFalse(
            self.policy.asset_candidate("https://cdn.example/files/pack.zip")
        )
        self.assertFalse(
            self.policy.page_candidate("https://forum.example/files/pack.zip", 1)
        )

    def test_default_excludes(self):
        self.assertFalse(
            self.policy.page_candidate("https://forum.example/login/", 1)
        )
        self.assertFalse(
            self.policy.page_candidate("https://forum.example/viewtopic.php?do=reply", 1)
        )
        self.assertFalse(
            self.policy.page_candidate("https://forum.example/search/", 1)
        )

    def test_path_prefix_and_include_exclude(self):
        policy = CrawlPolicy(
            seeds=["https://forum.example/"],
            path_prefixes=["/forum/"],
            include_patterns=["*/threads/*"],
            exclude_patterns=["*spam*"],
        )
        self.assertTrue(
            policy.page_candidate("https://forum.example/forum/threads/a.1/", 1)
        )
        self.assertFalse(
            policy.page_candidate("https://forum.example/forum/about/", 1)
        )
        self.assertFalse(
            policy.page_candidate("https://forum.example/forum/threads/spam.2/", 1)
        )

    def test_classify_page(self):
        self.assertEqual(
            self.policy.classify_page("https://forum.example/threads/a.1/"), "thread"
        )
        self.assertEqual(
            self.policy.classify_page("https://forum.example/forums/help.2/"), "forum"
        )
        self.assertEqual(
            self.policy.classify_page("https://forum.example/threads/a.1/page-2"), "thread"
        )


if __name__ == "__main__":
    unittest.main()
