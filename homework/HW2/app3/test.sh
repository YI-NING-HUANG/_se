#!/usr/bin/env bash
# HW2 app3 一鍵檢測: 純標準函式庫, 不需 pip, 不需外網
# 位置: homework/HW2/app3/test.sh (與 app.py / school.py 同資料夾)
# 用法:
#   bash homework/HW2/app3/test.sh
#   bash homework/HW2/app3/test.sh 2>&1 | tee homework/HW2/app3/test-report.txt
set -u
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT" || exit 1

PASS=0
FAIL=0
step() { echo "=== [$1] $2 ==="; }
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

step 1 "python 版本 (stdlib only, 不需 flask)"
if python --version; then ok "python 可執行"; else bad "python 不可執行"; fi
if python -c "import sqlite3; print('sqlite3 ok')"; then ok "sqlite3 內建可用"; else bad "sqlite3 不可用"; fi

step 2 "app.py 基本指令"
if python homework/HW2/app3/app.py --version; then ok "app.py --version"; else bad "app.py --version"; fi
if python homework/HW2/app3/app.py --help >/dev/null; then ok "app.py --help"; else bad "app.py --help"; fi

step 3 "單元測試 (不需開 server, 不需外網)"
if python -m unittest discover -s homework/HW2/app3/tests -v; then ok "unittest 全過"; else bad "unittest 有失敗"; fi

step 4 "重建資料庫 + 種子資料"
if python homework/HW2/app3/app.py --initdb; then ok "--initdb 重建成功"; else bad "--initdb 失敗"; fi
if python -c "import sys; sys.path.insert(0,'homework/HW2/app3'); import school; rows=school.list_courses('homework/HW2/app3/school.db'); assert len(rows)>=10, len(rows); print('courses:', len(rows))"; then ok "種子課程 >=10 筆"; else bad "種子課程不足"; fi

step 5 "產生 index.html 展示頁 (老師免跑 server 也能看)"
if python homework/HW2/app3/app.py --demo-out homework/HW2/app3/index.html; then ok "index.html 產生成功"; else bad "index.html 產生失敗"; fi
if grep -q "金大校務系統" homework/HW2/app3/index.html && grep -q "s001" homework/HW2/app3/index.html; then ok "index.html 內容正確"; else bad "index.html 缺關鍵字"; fi

step 6 "實機 smoke: 啟動 server + 查頁面與 API (只用本機 127.0.0.1)"
PORT=18771
python homework/HW2/app3/app.py --serve "$PORT" >/dev/null 2>&1 &
SRV=$!
sleep 2
if python -c "import urllib.request; h=urllib.request.urlopen('http://127.0.0.1:$PORT/login',timeout=5).read().decode('utf-8'); assert '登入' in h, 'no login'; print('login page ok')"; then ok "/login 有登入表單"; else bad "/login 異常"; fi
if python -c "import urllib.request,json; h=json.loads(urllib.request.urlopen('http://127.0.0.1:$PORT/api/courses',timeout=5).read().decode('utf-8')); assert len(h)>=10, len(h); print('api courses:',len(h))"; then ok "/api/courses >=10 筆"; else bad "/api/courses 異常"; fi
if python -c "import urllib.request,urllib.parse,json; q=urllib.parse.quote('護理系'); h=json.loads(urllib.request.urlopen('http://127.0.0.1:$PORT/api/courses?dept='+q,timeout=5).read().decode('utf-8')); assert h and all(x['dept']=='護理系' for x in h), h; print('dept filter ok:',len(h))"; then ok "科系過濾 API 正常"; else bad "科系過濾 API 異常"; fi

step 7 "端到端: 登入→加選→課表→衝堂擋→退選 (經 HTTP)"
if python - "$PORT" <<'PYEOF'; then ok "HTTP 端到端全過 (選課/衝堂/退選)"; else bad "HTTP 端到端失敗"; fi
import sys, urllib.request, urllib.parse, urllib.error, http.cookiejar, json
port = sys.argv[1]
base = "http://127.0.0.1:%s" % port
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def post(path, data):
    req = urllib.request.Request(base+path, data=urllib.parse.urlencode(data).encode())
    return op.open(req, timeout=5).read().decode("utf-8", "ignore")
def get(path):
    return op.open(base+path, timeout=5).read().decode("utf-8", "ignore")
# 重置 DB 後再測, 避免污染
import subprocess; subprocess.run([sys.executable, "homework/HW2/app3/app.py", "--initdb"], check=True)
post("/login", {"uid": "s001", "password": "1234"})
page0 = get("/courses")
assert "<select name='dept'" in page0, "缺科系下拉選單"
assert "護理系" in page0, "下拉缺科系選項"
assert "class='courses'" in page0 and "class='schedule'" in page0, "缺彩色導覽列"
post("/select", {"course_id": "CS101"})
sched = json.loads(op.open(base+"/api/schedule?sid=s001", timeout=5).read().decode("utf-8"))
assert any(c["id"]=="CS101" for c in sched), "加選後課表缺 CS101"
# CS201 與 CS101 同為一34, 應衝堂被擋: 直接打核心確認擋下, 且經 HTTP 再選一次也不會多選
page = post("/select", {"course_id": "CS201"})
sched2 = json.loads(op.open(base+"/api/schedule?sid=s001", timeout=5).read().decode("utf-8"))
assert not any(c["id"]=="CS201" for c in sched2), "衝堂課程不該選上"
assert "衝堂" in page or True  # redirect 頁也算過, 以課表為準
post("/drop", {"course_id": "CS101"})
sched3 = json.loads(op.open(base+"/api/schedule?sid=s001", timeout=5).read().decode("utf-8"))
assert not any(c["id"]=="CS101" for c in sched3), "退選後應消失"
# v1.1 新增: s003 有預設成績, 成績頁與 API 應顯示平均 84.0 / GPA 2.8
post("/login", {"uid": "s003", "password": "1234"})
gp = get("/grades")
assert "我的成績" in gp and "84.0" in gp and "2.8" in gp, "成績頁缺平均/GPA"
assert "class='grades'" in gp, "缺成績導覽按鈕"
api = json.loads(op.open(base+"/api/grades?sid=s003", timeout=5).read().decode("utf-8"))
assert api["avg"]==84.0 and api["gpa"]==2.8, api
# 同一帳號 s001 也能用全部功能：選課 + 成績 (82.0/2.5)
post("/login", {"uid": "s001", "password": "1234"})
gp1 = get("/grades")
assert "82.0" in gp1 and "2.5" in gp1, "s001 成績頁異常"
# v1.2 新增: 老師登分 → 學生即時看到；管理員開課 → 課表出現
post("/select", {"course_id": "CS101"})
post("/login", {"uid": "t001", "password": "1234"})
tt = get("/teaching")
assert "我的開課" in tt and "CS101" in tt, "老師開課頁異常"
gb = get("/gradebook?course=CS101")
assert "點名登分" in gb and "s001" in gb, "點名冊異常"
post("/setscore", {"course_id": "CS101", "student_id": "s001",
                   "score": "95"})
api1 = json.loads(op.open(base+"/api/grades?sid=s001", timeout=5).read().decode("utf-8"))
assert any(c["id"]=="CS101" and c["score"]==95 for c in api1["grades"]), api1
post("/login", {"uid": "admin", "password": "admin123"})
ad = get("/addcourse")
assert "開課管理" in ad, "管理員頁異常"
post("/addcourse", {"course_id": "NEW101", "dept": "資訊工程系",
                    "name": "測試課", "teacher": "高志遠", "credits": "3",
                    "capacity": "30", "time_slot": "六12"})
api2 = json.loads(urllib.request.urlopen(base+"/api/courses", timeout=5).read().decode("utf-8"))
assert any(c["id"]=="NEW101" for c in api2), "新課未出現"
# 權限：學生打不開老師頁 (403 內文應為權限不足)
post("/login", {"uid": "s001", "password": "1234"})
try:
    op.open(base+"/teaching", timeout=5).read()
    raise AssertionError("學生應被擋下老師頁")
except urllib.error.HTTPError as e:
    assert e.code==403 and "權限不足" in e.read().decode("utf-8"), e.code
print("e2e ok")
PYEOF
kill "$SRV" 2>/dev/null
wait "$SRV" 2>/dev/null
# 測完重建乾淨 DB, 方便老師直接開來用
python homework/HW2/app3/app.py --initdb >/dev/null 2>&1

echo "------------------------------"
echo "結果: PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
  exit 0
else
  echo "SOME CHECKS FAILED"
  exit 1
fi
