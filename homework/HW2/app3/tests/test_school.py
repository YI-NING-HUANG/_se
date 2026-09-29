"""app2 單元測試: 純 school.py 邏輯, 不需開 server, 不需外網."""
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
            # 先清空 s001 的預設成績選課, 還原「3 學分用完」的測試情境
            for c in school.get_schedule(self.db, "s001"):
                school.drop_course(self.db, "s001", c["id"])
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

    def test_grades_gpa(self):
        # s003 預設: GE101(2cr,88) PE101(1cr,92) EN101(2cr,76)
        # 平均=(176+92+152)/5=84.0, GPA=(6+4+4)/5=2.8
        avg, gpa, n = school.calc_gpa(self.db, "s003")
        self.assertEqual(n, 3)
        self.assertEqual(avg, 84.0)
        self.assertEqual(gpa, 2.8)

    def test_grades_all_accounts(self):
        # 三個帳號都有預設成績：s001(82.0/2.5), s002(86.25/3.25)
        avg, gpa, n = school.calc_gpa(self.db, "s001")
        self.assertEqual((avg, gpa, n), (82.0, 2.5, 2))
        avg, gpa, n = school.calc_gpa(self.db, "s002")
        self.assertEqual((avg, gpa, n), (86.25, 3.25, 2))


    def test_set_score(self):
        school.select_course(self.db, "s001", "CS101")
        ok, _ = school.set_score(self.db, "CS101", "s001", 90)
        self.assertTrue(ok)
        rows = school.get_grades(self.db, "s001")
        self.assertIn(90, [r["score"] for r in rows if r["id"] == "CS101"])
        ok, msg = school.set_score(self.db, "CS101", "s001", 101)
        self.assertFalse(ok)
        self.assertIn("0~100", msg)
        ok, msg = school.set_score(self.db, "CS101", "s002", 80)
        self.assertFalse(ok)
        self.assertIn("未選", msg)

    def test_teacher_courses_roster(self):
        rows = school.teacher_courses(self.db, "高志遠")
        ids = [c["id"] for c in rows]
        self.assertIn("CS101", ids)
        self.assertIn("CS201", ids)
        school.select_course(self.db, "s001", "CS101")
        roster = school.course_roster(self.db, "CS101")
        self.assertTrue(any(r["student_id"] == "s001" for r in roster))

    def test_add_course(self):
        ok, _ = school.add_course(self.db, "NEW101", "資訊工程系",
                                  "測試課", "高志遠", 3, 30, "六12")
        self.assertTrue(ok)
        self.assertTrue(any(c["id"] == "NEW101"
                            for c in school.list_courses(self.db)))
        ok, msg = school.add_course(self.db, "NEW101", "資訊工程系",
                                    "重複課", "高志遠", 3, 30, "六12")
        self.assertFalse(ok)
        self.assertIn("已存在", msg)
        ok, msg = school.add_course(self.db, "NEW102", "資訊工程系",
                                    "壞課", "高志遠", 0, 30, "六12")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
