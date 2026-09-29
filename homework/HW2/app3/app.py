#!/usr/bin/env python3
"""HW2 app3: 金大校務系統 v1.2 學生+老師+管理員 (純標準函式庫, 不需 pip).

用法:
  python app.py --initdb                 # 重建 school.db + 灌假資料
  python app.py --serve [PORT]           # 開網頁, 預設 8080, 只聽 127.0.0.1
  python app.py --demo-out index.html    # 產生靜態展示頁(老師免跑 server 也能看)
  python app.py --version / --help
"""
import argparse
import html
import json
import os
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer

import school

VERSION = "1.2.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "school.db")
HOME_BY_ROLE = {"student": "/courses", "teacher": "/teaching",
                "admin": "/addcourse"}


def current_sid(handler):
    cookie = handler.headers.get("Cookie", "")
    c = SimpleCookie()
    try:
        c.load(cookie)
    except Exception:
        return ""
    return c["sid"].value if "sid" in c else ""


def nav_for(role):
    base = "<a class='logout' href='/logout'>登出</a>"
    if role == "teacher":
        return ("<nav><a class='teaching' href='/teaching'>我的開課</a>"
                + base + "</nav><hr>")
    if role == "admin":
        return ("<nav><a class='addcourse' href='/addcourse'>開課管理</a>"
                "<a class='courses' href='/courses'>課程一覽</a>"
                + base + "</nav><hr>")
    return ("<nav><a class='courses' href='/courses'>課程</a>"
            "<a class='schedule' href='/schedule'>我的課表</a>"
            "<a class='grades' href='/grades'>我的成績</a>"
            + base + "</nav><hr>")


def send_html(handler, body, status=200, extra_headers=None, role="student"):
    data = ("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>金大校務系統 v1.2</title>"
            "<style>body{font-family:sans-serif;max-width:900px;margin:24px auto;"
            "padding:0 16px;background:#f7f9fc}"
            "table{border-collapse:collapse;width:100%;background:#fff}"
            "td,th{border:1px solid #ccc;padding:6px 8px;font-size:14px}"
            "th{background:#eef2f7}"
            "nav{background:#1a56db;padding:10px 12px;border-radius:8px}"
            "nav a{display:inline-block;margin-right:8px;padding:6px 14px;"
            "border-radius:6px;color:#fff;text-decoration:none;font-weight:bold}"
            "nav a.courses{background:#0b9e4b}nav a.schedule{background:#e67e0e}"
            "nav a.grades{background:#7c3aed}nav a.logout{background:#c0392b}"
            "nav a.teaching{background:#0e7490}nav a.addcourse{background:#4f46e5}"
            ".msg{color:#b00}</style>"
            "</head><body>"
            + nav_for(role) + body + "</body></html>")
    raw = data.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    for k, v in (extra_headers or {}).items():
        handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(raw)


def login_page(msg=""):
    m = "<p class='msg'>%s</p>" % html.escape(msg) if msg else ""
    return ("<h2>金大校務系統 v1.2 登入</h2>" + m +
            "<form method='post' action='/login'>"
            "帳號 <input name='uid' value='s001'> 密碼 "
            "<input type='password' name='password' value='1234'>"
            "<button>登入</button></form>"
            "<p>展示帳號：學生 s001/s002/s003（密碼 1234）; "
            "老師 t001/t002（密碼 1234）; 管理員 admin（密碼 admin123）</p>")


def courses_page(db, sid, msg="", keyword="", dept="", can_select=True):
    rows = school.list_courses(db, keyword, dept)
    depts = school.list_depts(db)
    m = "<p class='msg'>%s</p>" % html.escape(msg) if msg else ""
    q = html.escape(keyword)
    opts = "<option value=''>全部科系</option>" + "".join(
        "<option value='%s'%s>%s</option>" % (
            html.escape(d), " selected" if d == dept else "", html.escape(d))
        for d in depts)
    h = ["<h2>課程查詢 / 選課 (學號:%s)</h2>" % html.escape(sid), m,
         "<form method='get' action='/courses'>"
         "<select name='dept' onchange='this.form.submit()'>%s</select> "
         "<input name='q' value='%s' placeholder='課號/課名/老師'>"
         "<button>搜尋</button></form>" % (opts, q),
         "<table><tr><th>課號</th><th>科系</th><th>課名</th><th>老師</th><th>學分</th>"
         "<th>時間</th><th>已選/上限</th><th>操作</th></tr>"]
    for c in rows:
        if can_select:
            act = ("<form style='display:inline' method='post' action='/select'>"
                   "<input type='hidden' name='course_id' value='%s'>"
                   "<button>加選</button></form> "
                   "<form style='display:inline' method='post' action='/drop'>"
                   "<input type='hidden' name='course_id' value='%s'>"
                   "<button>退選</button></form>"
                   % (html.escape(c["id"]), html.escape(c["id"])))
        else:
            act = "-"
        h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%s</td>"
                 "<td>%s/%s</td><td>%s</td></tr>" % (
                     html.escape(c["id"]), html.escape(c["dept"]),
                     html.escape(c["name"]),
                     html.escape(c["teacher"]), c["credits"],
                     html.escape(c["time_slot"]), c["enrolled"], c["capacity"],
                     act))
    h.append("</table>")
    return "".join(h)


def schedule_page(db, sid, msg=""):
    rows = school.get_schedule(db, sid)
    total = sum(r["credits"] for r in rows)
    m = "<p class='msg'>%s</p>" % html.escape(msg) if msg else ""
    h = ["<h2>我的課表 (學號:%s, 共 %d 學分)</h2>" % (html.escape(sid), total), m,
         "<table><tr><th>課號</th><th>課名</th><th>學分</th><th>時間</th>"
         "<th>操作</th></tr>"]
    for c in rows:
        h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>"
                 "<form method='post' action='/drop'>"
                 "<input type='hidden' name='course_id' value='%s'>"
                 "<button>退選</button></form></td></tr>" % (
                     html.escape(c["id"]), html.escape(c["name"]),
                     c["credits"], html.escape(c["time_slot"]),
                     html.escape(c["id"])))
    h.append("</table>")
    return "".join(h)


def grades_page(db, sid):
    rows = school.get_grades(db, sid)
    avg, gpa, n = school.calc_gpa(db, sid)
    h = ["<h2>我的成績 (學號:%s)</h2>" % html.escape(sid)]
    if n:
        h.append("<p>已登分 %d 門, 學分加權平均 %s 分, GPA %s</p>"
                 % (n, avg, gpa))
    else:
        h.append("<p>尚無登分紀錄</p>")
    h.append("<table><tr><th>課號</th><th>科系</th><th>課名</th><th>學分</th>"
             "<th>分數</th><th>等第</th></tr>")
    for r in rows:
        sc = "尚未登分" if r["score"] is None else str(r["score"])
        pt = "-" if r["score"] is None else str(school.score_to_point(r["score"]))
        h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%s</td></tr>" % (
                     html.escape(r["id"]), html.escape(r["dept"]),
                     html.escape(r["name"]), r["credits"], sc, pt))
    h.append("</table>")
    return "".join(h)


def teaching_page(db, user, msg=""):
    rows = school.teacher_courses(db, user["name"])
    m = "<p class='msg'>%s</p>" % html.escape(msg) if msg else ""
    h = ["<h2>我的開課 (老師:%s)</h2>" % html.escape(user["name"]), m,
         "<table><tr><th>課號</th><th>科系</th><th>課名</th><th>學分</th>"
         "<th>時間</th><th>已選/上限</th><th>登分</th></tr>"]
    for c in rows:
        h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%s/%s</td>"
                 "<td><a href='/gradebook?course=%s'>點名登分</a></td></tr>" % (
                     html.escape(c["id"]), html.escape(c["dept"]),
                     html.escape(c["name"]), c["credits"],
                     html.escape(c["time_slot"]), c["enrolled"], c["capacity"],
                     urllib.parse.quote(c["id"])))
    h.append("</table>")
    return "".join(h)


def gradebook_page(db, course_id, msg=""):
    roster = school.course_roster(db, course_id)
    m = "<p class='msg'>%s</p>" % html.escape(msg) if msg else ""
    h = ["<h2>點名登分 (%s)</h2>" % html.escape(course_id), m,
         "<table><tr><th>學號</th><th>姓名</th><th>目前分數</th><th>登分</th></tr>"]
    for r in roster:
        sc = "尚未登分" if r["score"] is None else str(r["score"])
        h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>"
                 "<form method='post' action='/setscore'>"
                 "<input type='hidden' name='course_id' value='%s'>"
                 "<input type='hidden' name='student_id' value='%s'>"
                 "<input name='score' size='4' placeholder='0~100'>"
                 "<button>送出</button></form></td></tr>" % (
                     html.escape(r["student_id"]),
                     html.escape(r["student_name"]), sc,
                     html.escape(course_id),
                     html.escape(r["student_id"])))
    if not roster:
        h.append("<tr><td colspan='4'>尚無學生選此課程</td></tr>")
    h.append("</table>")
    return "".join(h)


def addcourse_page(db, msg=""):
    depts = school.list_depts(db)
    opts = "".join("<option>%s</option>" % html.escape(d) for d in depts)
    m = "<p class='msg'>%s</p>" % html.escape(msg) if msg else ""
    return ("<h2>開課管理 (管理員)</h2>" + m +
            "<form method='post' action='/addcourse'>"
            "課號 <input name='course_id'> "
            "科系 <select name='dept'>%s</select><br>"
            "課名 <input name='name'> 老師 <input name='teacher'><br>"
            "學分 <input name='credits' size='3' value='3'> "
            "上限 <input name='capacity' size='4' value='30'> "
            "時間 <input name='time_slot' size='6' placeholder='一34'><br>"
            "<button>新增課程</button></form>" % opts)


class Handler(BaseHTTPRequestHandler):
    server_version = "NQU-School/1.0"

    def log_message(self, *a):
        pass  # 保持 test.sh 輸出乾淨

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        path, qs = url.path, urllib.parse.parse_qs(url.query)
        sid = current_sid(self)
        if path == "/api/courses":
            data = json.dumps(school.list_courses(DB_PATH,
                              qs.get("q", [""])[0], qs.get("dept", [""])[0]),
                              ensure_ascii=False)
            raw = data.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/schedule":
            who = qs.get("sid", [sid])[0]
            data = json.dumps(school.get_schedule(DB_PATH, who),
                              ensure_ascii=False)
            raw = data.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/" :
            user = school.get_user(DB_PATH, sid) if sid else None
            home = HOME_BY_ROLE.get(user["role"], "/courses") if user else "/login"
            self.send_response(302)
            self.send_header("Location", home)
            self.end_headers()
            return
        if path == "/login":
            send_html(self, login_page())
            return
        if path == "/logout":
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header("Set-Cookie", "sid=; Path=/; Max-Age=0")
            self.end_headers()
            return
        if not sid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        user = school.get_user(DB_PATH, sid)
        if not user:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        role = user["role"]
        deny = lambda: send_html(self, "<h2>權限不足</h2>"
                                 "<p>此頁僅限特定角色</p>", 403, role=role)
        if path == "/courses":
            send_html(self, courses_page(DB_PATH, sid,
                      qs.get("msg", [""])[0], qs.get("q", [""])[0],
                      qs.get("dept", [""])[0],
                      can_select=(role == "student")), role=role)
            return
        if path == "/schedule" and role == "student":
            send_html(self, schedule_page(DB_PATH, sid,
                      qs.get("msg", [""])[0]), role=role)
            return
        if path == "/grades" and role == "student":
            send_html(self, grades_page(DB_PATH, sid), role=role)
            return
        if path == "/teaching" and role == "teacher":
            send_html(self, teaching_page(DB_PATH, user,
                      qs.get("msg", [""])[0]), role=role)
            return
        if path == "/gradebook" and role == "teacher":
            course = qs.get("course", [""])[0]
            mine = [c["id"] for c in school.teacher_courses(
                DB_PATH, user["name"])]
            if course not in mine:
                deny()
                return
            send_html(self, gradebook_page(DB_PATH, course,
                      qs.get("msg", [""])[0]), role=role)
            return
        if path == "/addcourse" and role == "admin":
            send_html(self, addcourse_page(DB_PATH,
                      qs.get("msg", [""])[0]), role=role)
            return
        if path in ("/schedule", "/grades") and role != "student":
            deny()
            return
        if path in ("/teaching", "/gradebook") and role != "teacher":
            deny()
            return
        if path == "/addcourse" and role != "admin":
            deny()
            return
        if path == "/api/grades":
            who = qs.get("sid", [sid])[0]
            data = json.dumps({"grades": school.get_grades(DB_PATH, who),
                               "avg": school.calc_gpa(DB_PATH, who)[0],
                               "gpa": school.calc_gpa(DB_PATH, who)[1]},
                              ensure_ascii=False)
            raw = data.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        fields = urllib.parse.parse_qs(
            self.rfile.read(length).decode("utf-8", "ignore"))
        get = lambda k: fields.get(k, [""])[0]
        if path == "/login":
            user = school.verify_user(DB_PATH, get("uid"), get("password"))
            if user:
                self.send_response(302)
                self.send_header(
                    "Location", HOME_BY_ROLE.get(user["role"], "/courses"))
                self.send_header("Set-Cookie",
                                 "sid=%s; Path=/" % user["id"])
                self.end_headers()
            else:
                send_html(self, login_page("帳號或密碼錯誤"))
            return
        sid = current_sid(self)
        if not sid:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        user = school.get_user(DB_PATH, sid)
        if not user:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        role = user["role"]
        if path == "/select" and role == "student":
            ok, msg = school.select_course(DB_PATH, sid, get("course_id"))
            dest = "/courses?msg=" + urllib.parse.quote(msg)
            self.send_response(302)
            self.send_header("Location", dest)
            self.end_headers()
            return
        if path == "/drop" and role == "student":
            ok, msg = school.drop_course(DB_PATH, sid, get("course_id"))
            dest = "/schedule?msg=" + urllib.parse.quote(msg)
            self.send_response(302)
            self.send_header("Location", dest)
            self.end_headers()
            return
        if path == "/setscore" and role == "teacher":
            course = get("course_id")
            mine = [c["id"] for c in school.teacher_courses(
                DB_PATH, user["name"])]
            if course in mine:
                ok, msg = school.set_score(DB_PATH, course,
                                           get("student_id"), get("score"))
            else:
                ok, msg = False, "只能替自己的課程登分"
            dest = ("/gradebook?course=" + urllib.parse.quote(course)
                    + "&msg=" + urllib.parse.quote(msg))
            self.send_response(302)
            self.send_header("Location", dest)
            self.end_headers()
            return
        if path == "/addcourse" and role == "admin":
            ok, msg = school.add_course(DB_PATH, get("course_id"),
                                        get("dept"), get("name"),
                                        get("teacher"), get("credits"),
                                        get("capacity"), get("time_slot"))
            dest = "/addcourse?msg=" + urllib.parse.quote(msg)
            self.send_response(302)
            self.send_header("Location", dest)
            self.end_headers()
            return
        send_html(self, "<h2>權限不足</h2><p>此操作僅限特定角色</p>",
                  403, role=role)


def build_parser():
    p = argparse.ArgumentParser(description="金大校務系統 v1.2 (stdlib only)")
    p.add_argument("--serve", nargs="?", const=8080, type=int, metavar="PORT",
                   help="啟動網頁 (預設只聽 127.0.0.1, 對外用 --host 0.0.0.0)")
    p.add_argument("--port", type=int, default=None, help="同 --serve 的埠號")
    p.add_argument("--host", default="127.0.0.1",
                   help="綁定位址: 127.0.0.1=只自己能開, 0.0.0.0=同 Wi-Fi 可開")
    p.add_argument("--initdb", action="store_true", help="重建 school.db")
    p.add_argument("--demo-out", metavar="FILE", help="產生靜態展示頁")
    p.add_argument("--version", action="store_true")
    return p


def make_demo(out_path):
    report = ""
    rp = os.path.join(BASE_DIR, "test-report.txt")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8", errors="ignore") as f:
            report = f.read()
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                   "<td>%s</td><td>%s</td><td>%s</td></tr>" % c
                   for c in school.SEED_COURSES)
    body = """<h1>金大校務系統 v1.2 (app3 學生+老師+管理員)</h1>
<p>純 Python 標準函式庫 + sqlite3, 不需 pip install。展示帳號: s001/1234。</p>
<h2>啟動</h2><pre>python app.py --initdb
python app.py --serve 8080
# 開 http://127.0.0.1:8080/ </pre>
<h2>功能</h2><ul><li>登入/登出</li><li>課程查詢：科系下拉選單 + 關鍵字搜尋</li>
<li>加選/退選, 擋修: 額滿/衝堂/學分上限(%d)/重複</li><li>我的課表與學分統計</li><li>我的成績：分數查詢 + 學分加權平均 + GPA (三個帳號都有預設成績)</li>
<li>老師 (t001/t002)：我的開課 + 點名登分/改分</li>
<li>管理員 (admin)：開課管理 (新增課程)</li></ul>
<h2>預設課程</h2><table>
<tr><th>課號</th><th>科系</th><th>課名</th><th>老師</th><th>學分</th><th>上限</th><th>時間</th></tr>%s</table>
<h2>檢測報告 (test-report.txt)</h2><pre>%s</pre>""" % (
        school.MAX_CREDITS, rows, html.escape(report))
    page = ("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
            "<title>金大校務系統 v1.2 展示</title></head><body>%s</body></html>"
            % body)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print("已產生 %s" % out_path)


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.version:
        print("nqu-school-app3 %s (python stdlib only)" % VERSION)
        return 0
    if args.initdb:
        school.seed_db(DB_PATH)
        print("已重建 %s" % DB_PATH)
        return 0
    if args.demo_out:
        make_demo(args.demo_out)
        return 0
    port = args.serve if args.serve else args.port
    if port:
        if not os.path.exists(DB_PATH):
            school.seed_db(DB_PATH)
        host = args.host
        srv = HTTPServer((host, int(port)), Handler)
        print("serving http://%s:%d/ (Ctrl-C 停止)" % (host, int(port)))
        if host == "0.0.0.0":
            import socket
            try:
                lan = socket.gethostbyname(socket.gethostname())
            except Exception:
                lan = "你的區網IP"
            print("同 Wi-Fi 的人開 http://%s:%d/ (需同網路+防火牆放行)"
                  % (lan, int(port)))
            print("注意: 127.0.0.1 只代表你自己這台, 別人打不開是正常的; "
                  "要給全網際網路的人開需部署上雲 (見 README)。")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
