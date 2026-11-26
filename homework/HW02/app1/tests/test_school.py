"""app1 單元測試: 純 school.py 邏輯, 不需開 server, 不需外網."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import school


class SchoolTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        school.seed_db(self.db)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_login_ok(self):
        self.assertIsNotNone(school.verify_user(self.db, "s001", "1234"))

    def test_login_fail(self):
        self.assertIsNone(school.verify_user(self.db, "s001", "wrong"))

    def test_select_ok(self):
        ok, _ = school.select_course(self.db, "s001", "CS101")
        self.assertTrue(ok)
        ids = [c["id"] for c in school.get_schedule(self.db, "s001")]
        self.assertIn("CS101", ids)

    def test_select_duplicate(self):
        school.select_course(self.db, "s001", "CS101")
        ok, msg = school.select_course(self.db, "s001", "CS101")
        self.assertFalse(ok)
        self.assertIn("已選", msg)

    def test_select_conflict(self):
        # CS101(一34) 與 CS201(一34) 衝堂
        school.select_course(self.db, "s001", "CS101")
        ok, msg = school.select_course(self.db, "s001", "CS201")
        self.assertFalse(ok)
        self.assertIn("衝堂", msg)

    def test_select_full(self):
        # CS101 上限 2 人, s001+s002 選滿, s003 應被擋
        school.select_course(self.db, "s001", "CS101")
        school.select_course(self.db, "s002", "CS101")
        ok, msg = school.select_course(self.db, "s003", "CS101")
        self.assertFalse(ok)
        self.assertIn("已滿", msg)

    def test_select_credit_limit(self):
        old = school.MAX_CREDITS
        school.MAX_CREDITS = 3
        try:
            school.select_course(self.db, "s001", "CS102")  # 3 學分用完
            ok, msg = school.select_course(self.db, "s001", "CS202")
            self.assertFalse(ok)
            self.assertIn("學分", msg)
        finally:
            school.MAX_CREDITS = old

    def test_drop(self):
        school.select_course(self.db, "s001", "CS101")
        ok, _ = school.drop_course(self.db, "s001", "CS101")
        self.assertTrue(ok)
        ok, _ = school.drop_course(self.db, "s001", "CS101")
        self.assertFalse(ok)

    def test_search(self):
        rows = school.list_courses(self.db, "資料")
        self.assertTrue(any("資料" in r["name"] for r in rows))

    def test_dept_filter(self):
        rows = school.list_courses(self.db, dept="護理系")
        self.assertTrue(rows)
        self.assertTrue(all(r["dept"] == "護理系" for r in rows))
        self.assertTrue(any(r["id"] == "NR201" for r in rows))
        depts = school.list_depts(self.db)
        self.assertIn("資訊工程系", depts)
        self.assertIn("觀光管理系", depts)
        combo = school.list_courses(self.db, "資料", "資訊工程系")
        self.assertTrue(combo)
        self.assertTrue(all(r["dept"] == "資訊工程系" for r in combo))


if __name__ == "__main__":
    unittest.main()
