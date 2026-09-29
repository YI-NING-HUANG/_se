"""HW2 app3: 校務系統 v1.2 (學生選課成績 + 老師登分 + 管理員開課).

被 app.py (網頁) 與 tests/test_school.py (單元測試) 共用,
不含任何 HTTP 程式碼, 方便測試.
"""
import os
import sqlite3

MAX_CREDITS = 25
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

SEED_USERS = [
    # 以下皆為虛構人物, 與現實無關 (展示用假帳號)
    # 學生密碼皆 1234；老師 t001/t002 密碼 1234；管理員 admin123
    ("s001", "金小奕", "1234", "student"),
    ("s002", "門小寧", "1234", "student"),
    ("s003", "沙小安", "1234", "student"),
    ("t001", "高志遠", "1234", "teacher"),  # 任教 CS101/CS201 (與課程 teacher 同名)
    ("t002", "韓美玲", "1234", "teacher"),  # 任教 BA201
    ("admin", "系統管理員", "admin123", "admin"),
]

SEED_COURSES = [
    # id, dept, name, teacher(虛構), credits, capacity, time_slot(星期+節次)
    # 注意: CS101/CS201 刻意同為一34(衝堂測試用), CS101 上限 2 人(額滿測試用),
    # 改種子時請保留這幾個關鍵欄位, 否則 tests/ 會失敗.
    ("CS101", "資訊工程系", "程式設計(一)", "高志遠", 3, 2, "一34"),
    ("CS102", "資訊工程系", "計算機概論", "林曉峰", 3, 30, "二12"),
    ("CS201", "資訊工程系", "資料結構", "高志遠", 3, 30, "一34"),  # 與 CS101 衝堂
    ("CS202", "資訊工程系", "離散數學", "趙文琪", 3, 30, "三34"),
    ("CS301", "資訊工程系", "作業系統", "蔡佩君", 3, 30, "五34"),
    ("CS302", "資訊工程系", "資料庫系統", "許明哲", 3, 30, "二34"),
    ("EE201", "電機工程系", "電路學", "謝宗翰", 3, 35, "一12"),
    ("BA201", "企業管理系", "企業管理概論", "韓美玲", 3, 40, "二56"),
    ("TM301", "觀光管理系", "觀光行銷學", "羅國華", 3, 40, "三56"),
    ("FS201", "食品科學系", "食品化學", "潘淑芬", 3, 35, "四56"),
    ("NR201", "護理系", "基本護理學", "蔣心怡", 3, 30, "五12"),
    ("HS101", "社會工作系", "社會工作概論", "馮建國", 2, 45, "四12"),
    ("GE101", "通識中心", "金門學概論", "鄭雅婷", 2, 50, "三12"),
    ("PE101", "體育室", "體育(一)", "黃俊傑", 1, 40, "四34"),
    ("EN101", "語文中心", "英文(一)", "劉怡君", 2, 40, "五56"),
]


def connect(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def init_db(db_path):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()
    con = connect(db_path)
    try:
        con.executescript(schema)
        con.commit()
    finally:
        con.close()


def seed_db(db_path):
    """重建並灌假資料, 供 app.py --initdb 與測試使用."""
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
    con = connect(db_path)
    try:
        con.executemany(
            "INSERT INTO users(id,name,password,role) VALUES(?,?,?,?)", SEED_USERS
        )
        con.executemany(
            "INSERT INTO courses(id,dept,name,teacher,credits,capacity,time_slot)"
            " VALUES(?,?,?,?,?,?,?)",
            SEED_COURSES,
        )
        # 展示用已登分紀錄：三個帳號都有，登入任一個都能用成績功能.
        # 注意：避開一34 (CS101/CS201 衝堂測試用) 與 CS102/CS202 (學分測試用)，
        # 否則 tests/ 的選課測試會被擋下.
        con.executemany(
            "INSERT INTO enrollments(student_id,course_id,score)"
            " VALUES(?,?,?)",
            [("s001", "GE101", 88),
             ("s001", "EN101", 76),
             ("s002", "BA201", 85),
             ("s002", "PE101", 90),
             ("s003", "GE101", 88),
             ("s003", "PE101", 92),
             ("s003", "EN101", 76)],
        )
        con.commit()
    finally:
        con.close()


def verify_user(db_path, uid, password):
    con = connect(db_path)
    try:
        row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if row and row["password"] == password:
            return dict(row)
        return None
    finally:
        con.close()


def list_courses(db_path, keyword="", dept=""):
    con = connect(db_path)
    try:
        conds, args = [], []
        if keyword:
            kw = "%" + keyword + "%"
            conds.append("(c.id LIKE ? OR c.name LIKE ? OR c.teacher LIKE ?)")
            args += [kw, kw, kw]
        if dept:
            conds.append("c.dept=?")
            args.append(dept)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        rows = con.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM enrollments e"
            " WHERE e.course_id=c.id) AS enrolled"
            " FROM courses c" + where + " ORDER BY c.id",
            args,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def list_depts(db_path):
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT DISTINCT dept FROM courses ORDER BY dept").fetchall()
        return [r["dept"] for r in rows]
    finally:
        con.close()


def get_schedule(db_path, student_id):
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT c.* FROM courses c JOIN enrollments e"
            " ON e.course_id=c.id WHERE e.student_id=? ORDER BY c.id",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def total_credits(db_path, student_id):
    return sum(c["credits"] for c in get_schedule(db_path, student_id))


def time_conflict(a, b):
    """time_slot 格式: 首字星期 + 節次, 如 '一34'. 同星期且節次交集即衝堂."""
    if not a or not b:
        return False
    if a[0] != b[0]:
        return False
    return bool(set(a[1:]) & set(b[1:]))


def select_course(db_path, student_id, course_id):
    """回傳 (ok, msg). 擋修順序: 存在/重複/額滿/衝堂/學分上限."""
    con = connect(db_path)
    try:
        course = con.execute(
            "SELECT * FROM courses WHERE id=?", (course_id,)
        ).fetchone()
        if not course:
            return False, "查無此課程"
        dup = con.execute(
            "SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",
            (student_id, course_id),
        ).fetchone()
        if dup:
            return False, "已選過此課程"
        enrolled = con.execute(
            "SELECT COUNT(*) AS n FROM enrollments WHERE course_id=?",
            (course_id,),
        ).fetchone()["n"]
        if enrolled >= course["capacity"]:
            return False, "人數已滿"
        mine = con.execute(
            "SELECT c.time_slot, c.credits FROM courses c"
            " JOIN enrollments e ON e.course_id=c.id WHERE e.student_id=?",
            (student_id,),
        ).fetchall()
        for m in mine:
            if time_conflict(m["time_slot"], course["time_slot"]):
                return False, "衝堂: 與已選課程時間重疊"
        total = sum(m["credits"] for m in mine) + course["credits"]
        if total > MAX_CREDITS:
            return False, "超過學分上限(%d)" % MAX_CREDITS
        con.execute(
            "INSERT INTO enrollments(student_id,course_id) VALUES(?,?)",
            (student_id, course_id),
        )
        con.commit()
        return True, "選課成功"
    finally:
        con.close()


def drop_course(db_path, student_id, course_id):
    con = connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM enrollments WHERE student_id=? AND course_id=?",
            (student_id, course_id),
        )
        con.commit()
        if cur.rowcount:
            return True, "退選成功"
        return False, "原本就沒選此課程"
    finally:
        con.close()


def score_to_point(score):
    if score is None:
        return None
    if score >= 90:
        return 4.0
    if score >= 80:
        return 3.0
    if score >= 70:
        return 2.0
    if score >= 60:
        return 1.0
    return 0.0


def get_user(db_path, uid):
    con = connect(db_path)
    try:
        row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def teacher_courses(db_path, teacher_name):
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM enrollments e"
            " WHERE e.course_id=c.id) AS enrolled"
            " FROM courses c WHERE c.teacher=? ORDER BY c.id",
            (teacher_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def course_roster(db_path, course_id):
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT u.id AS student_id, u.name AS student_name, e.score"
            " FROM enrollments e JOIN users u ON u.id=e.student_id"
            " WHERE e.course_id=? ORDER BY u.id",
            (course_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def set_score(db_path, course_id, student_id, score):
    """老師登分/改分. 回傳 (ok, msg)."""
    try:
        score = int(score)
    except (TypeError, ValueError):
        return False, "分數須為 0~100 的整數"
    if not 0 <= score <= 100:
        return False, "分數須為 0~100 的整數"
    con = connect(db_path)
    try:
        hit = con.execute(
            "SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?",
            (student_id, course_id),
        ).fetchone()
        if not hit:
            return False, "該學生未選此課程"
        con.execute(
            "UPDATE enrollments SET score=? WHERE student_id=? AND course_id=?",
            (score, student_id, course_id),
        )
        con.commit()
        return True, "登分成功"
    finally:
        con.close()


def add_course(db_path, cid, dept, name, teacher, credits, capacity,
               time_slot):
    """管理員開課. 回傳 (ok, msg)."""
    if not all([cid, dept, name, teacher, time_slot]):
        return False, "課號/科系/課名/老師/時間不可空白"
    try:
        credits, capacity = int(credits), int(capacity)
    except (TypeError, ValueError):
        return False, "學分與上限須為正整數"
    if credits <= 0 or capacity <= 0:
        return False, "學分與上限須為正整數"
    con = connect(db_path)
    try:
        dup = con.execute("SELECT 1 FROM courses WHERE id=?",
                          (cid,)).fetchone()
        if dup:
            return False, "課號已存在"
        con.execute(
            "INSERT INTO courses(id,dept,name,teacher,credits,capacity,"
            "time_slot) VALUES(?,?,?,?,?,?,?)",
            (cid, dept, name, teacher, credits, capacity, time_slot),
        )
        con.commit()
        return True, "開課成功"
    finally:
        con.close()


def get_grades(db_path, student_id):
    """已選課程含分數 (score 為 None 表尚未登分)."""
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT c.id, c.dept, c.name, c.credits, e.score"
            " FROM courses c JOIN enrollments e ON e.course_id=c.id"
            " WHERE e.student_id=? ORDER BY c.id",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def calc_gpa(db_path, student_id):
    """回傳 (avg百分制, gpa, n_graded). 只計已登分課程, 依學分加權."""
    rows = [r for r in get_grades(db_path, student_id)
            if r["score"] is not None]
    if not rows:
        return None, None, 0
    tot_cr = sum(r["credits"] for r in rows)
    avg = sum(r["score"] * r["credits"] for r in rows) / tot_cr
    gpa = sum(score_to_point(r["score"]) * r["credits"] for r in rows) / tot_cr
    return round(avg, 2), round(gpa, 2), len(rows)
