#!/usr/bin/env python3
"""HW2 docs 展示頁產生器 (純標準函式庫).

把 app1 的種子課程 + test-report.txt 包成靜態網頁,
雙擊 file:// 能看, 推上 GitHub Pages 用連結也能看.
與 app1/app2... 版本資料夾完全區隔, 不參與版本門檻.

用法:
  python homework/HW2/docs/build.py
"""
import html
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP1_DIR = os.path.join(BASE_DIR, "..", "app1")
sys.path.insert(0, APP1_DIR)
import school  # noqa: E402

PAGES_URL = "https://yi-ning-huang.github.io/_se/homework/HW2/docs/"
VERSION = "1.0.0"

CSS = ("body{font-family:sans-serif;max-width:960px;margin:24px auto;"
       "padding:0 16px;line-height:1.7}table{border-collapse:collapse;width:100%}"
       "td,th{border:1px solid #ccc;padding:6px 8px;font-size:14px}"
       "th{background:#f2f2f2}pre{background:#f6f6f6;padding:12px;overflow:auto}"
       "nav a{margin-right:12px}")


def page(title, body):
    return ("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style></head>"
            "<body><nav><a href='index.html'>展示首頁</a>"
            "<a href='school.html'>school.py 原始碼</a>"
            "<a href='app.html'>app.py 原始碼</a></nav><hr>%s</body></html>"
            % (html.escape(title), CSS, body))


def source_page(path, title):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    body = "<h1>%s (%d 行)</h1><pre>%s</pre>" % (
        html.escape(title), len(src.splitlines()), html.escape(src))
    return page(title, body)


def main():
    report_path = os.path.join(APP1_DIR, "test-report.txt")
    report = ""
    if os.path.exists(report_path):
        with open(report_path, encoding="utf-8", errors="ignore") as f:
            report = f.read()
    students = "".join(
        "<tr><td>%s</td><td>%s</td><td>1234</td></tr>" % (u[0], u[1])
        for u in school.SEED_USERS)
    courses = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
        "<td>%s</td></tr>"
        % c for c in school.SEED_COURSES)
    body = """<h1>金大校務系統 v%s 展示頁</h1>
<p>純 Python 標準函式庫 + sqlite3, 不需 pip install。
本專案所有人名皆為<b>虛構假名</b>, 與現實人物無關。
課程橫跨多系所 (資工/電機/企管/觀光/食品/護理/社工/通識/體育/語文),
取材自綜合型大學常見開課, 非單一系所。</p>
<h2>怎麼看</h2>
<ul><li><b>本機雙擊</b>: 直接用瀏覽器開這個 <code>index.html</code> (免網路免 server)。</li>
<li><b>用連結</b>: 推上 GitHub 後開 <a href="{pages}">{pages}</a>。</li>
<li><b>實際操作</b> (登入/選課/退選需跑 server):
<pre>python homework/HW2/app1/app.py --initdb
python homework/HW2/app1/app.py --serve 8080
# 開 http://127.0.0.1:8080/ (同 Wi-Fi 加 --host 0.0.0.0)</pre></li></ul>
<h2>展示帳號 (密碼皆 1234)</h2>
<table><tr><th>學號</th><th>姓名(假名)</th><th>密碼</th></tr>{students}</table>
<h2>預設課程 ({n} 門)</h2>
<table><tr><th>課號</th><th>科系</th><th>課名</th><th>老師(假名)</th><th>學分</th><th>上限</th><th>時間</th></tr>{courses}</table>
<h2>版一功能 (app1 選課核心)</h2>
<ul><li>登入/登出</li><li>課程查詢：科系下拉選單 + 關鍵字搜尋</li>
<li>加選/退選, 擋修: 額滿 / 衝堂 / 學分上限({maxcr}) / 重複</li>
<li>我的課表與學分統計</li></ul>
<h2>v1.1 新增 (app2)</h2>
<ul><li>我的成績：分數查詢 + 等第 + 學分加權平均 + GPA (三個帳號都有預設成績，如 s003：平均 84.0 / GPA 2.8)</li></ul>
<h2>v1.2 新增 (app3)</h2>
<ul><li>老師 (t001/t002)：我的開課 + 點名登分/改分</li>
<li>管理員 (admin)：開課管理；導覽列按角色顯示，跨權限擋下</li></ul>
<h2>版本對照</h2>
<table><tr><th>版</th><th>資料夾</th><th>內容</th></tr>
<tr><td>v1.0</td><td>app1/</td><td>選課核心 (主要功能, test.sh 門檻)</td></tr>
<tr><td>v1.1</td><td>app2/</td><td>app1 + 成績查詢/GPA (test.sh 門檻含回歸)</td></tr>
<tr><td>v1.2</td><td>app3/</td><td>app2 + 老師登分 + 管理員開課 (test.sh 門檻含回歸)</td></tr>
<tr><td>展示</td><td>docs/ (本頁)</td><td>靜態展示, 不參與版本門檻</td></tr></table>
<h2>檢測報告 (app1/test-report.txt)</h2><pre>{report}</pre>
<h2>原始碼瀏覽</h2>
<ul><li><a href='school.html'>school.py</a> (核心邏輯)</li>
<li><a href='app.html'>app.py</a> (網頁層)</li></ul>""".format(
        VERSION, pages=PAGES_URL, students=students, courses=courses,
        n=len(school.SEED_COURSES), maxcr=school.MAX_CREDITS,
        report=html.escape(report))
    with open(os.path.join(BASE_DIR, "index.html"), "w",
              encoding="utf-8") as f:
        f.write(page("金大校務系統 v%s 展示" % VERSION, body))
    with open(os.path.join(BASE_DIR, "school.html"), "w",
              encoding="utf-8") as f:
        f.write(source_page(os.path.join(APP1_DIR, "school.py"), "school.py"))
    with open(os.path.join(BASE_DIR, "app.html"), "w",
              encoding="utf-8") as f:
        f.write(source_page(os.path.join(APP1_DIR, "app.py"), "app.py"))
    print("docs 已產生: index.html + school.html + app.html")


if __name__ == "__main__":
    main()
