"""HW2 app1: 校務系統選課核心邏輯 (純標準函式庫 + sqlite3).

被 app.py (網頁) 與 tests/test_school.py (單元測試) 共用,
不含任何 HTTP 程式碼, 方便測試.
"""
import os
import sqlite3

MAX_CREDITS = 25
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

SEED_USERS = [
    # 以下皆為虛構人物, 與現實無關 (展示用假帳號, 密碼皆 1234)
    ("s001", "金小奕", "1234", "student"),
    ("s002", "門小寧", "1234", "student"),
    ("s003", "沙小安", "1234", "student"),
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
