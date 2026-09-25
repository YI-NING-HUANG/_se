#!/usr/bin/env bash
# HW1 mycurl 一鍵檢測: 確認整個程式可以跑動
# 位置: homework/HW1/mycurl/test.sh (與 mycurl.py / mycurl2.py 同資料夾)
# 用法:
#   bash homework/HW1/mycurl/test.sh
#   bash homework/HW1/mycurl/test.sh 2>&1 | tee homework/HW1/mycurl/test-report.txt
set -u
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8  # 檢測報告固定 utf-8, 方便內嵌到網頁

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT" || exit 1

PASS=0
FAIL=0
step() { echo "=== [$1] $2 ==="; }
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

step 1 "python 版本"
if python --version; then ok "python 可執行"; else bad "python 不可執行"; fi

step 2 "mycurl.py 基本指令"
if python homework/HW1/mycurl/mycurl.py --version; then ok "mycurl.py --version"; else bad "mycurl.py --version"; fi
if python homework/HW1/mycurl/mycurl.py --help >/dev/null; then ok "mycurl.py --help"; else bad "mycurl.py --help"; fi

step 3 "mycurl2.py 基本指令 (超集參數)"
if python homework/HW1/mycurl/mycurl2.py --version; then ok "mycurl2.py --version"; else bad "mycurl2.py --version"; fi
if python homework/HW1/mycurl/mycurl2.py --help | grep -q -- "--serve" && python homework/HW1/mycurl/mycurl2.py --help | grep -q -- "--html-out"; then ok "mycurl2.py 有 --serve/--html-out"; else bad "mycurl2.py 缺網頁參數"; fi

step 4 "單元測試 (本機 http.server, 不需外網)"
if python -m unittest discover -s homework/HW1/mycurl/tests -v; then ok "unittest 全過"; else bad "unittest 有失敗"; fi

step 5 "mycurl2.py 產生 index.html 介紹頁"
if python homework/HW1/mycurl/mycurl2.py --demo-out homework/HW1/mycurl/index.html; then ok "index.html 產生成功"; else bad "index.html 產生失敗"; fi
if grep -q "mycurl2" homework/HW1/mycurl/index.html && grep -q "NoRedirect" homework/HW1/mycurl/index.html; then ok "index.html 內容正確 (含 mycurl2 與原始碼)"; else bad "index.html 內容缺關鍵字"; fi

step 6 "實機 CLI: 本機 http.server + mycurl.py GET"
PORT=18765
python -m http.server "$PORT" --directory "$ROOT" >/dev/null 2>&1 &
SRV=$!
sleep 2
if python homework/HW1/mycurl/mycurl.py "http://127.0.0.1:$PORT/homework/HW1/mycurl/README.md" -s -o "$SCRIPT_DIR/.smoke.out"; then
  if grep -q "mycurl" "$SCRIPT_DIR/.smoke.out"; then ok "實機 GET 成功 (本機 server 取回 README)"; else bad "實機 GET 回傳內容不符"; fi
else
  bad "實機 GET 執行失敗"
fi
rm -f "$SCRIPT_DIR/.smoke.out"
kill "$SRV" 2>/dev/null
wait "$SRV" 2>/dev/null

step 7 "mycurl vs mycurl2 輸出一致 (同一請求)"
PORT2=18766
python -m http.server "$PORT2" --directory "$ROOT" >/dev/null 2>&1 &
SRV2=$!
sleep 2
U2="http://127.0.0.1:$PORT2/homework/HW1/mycurl/README.md"
python homework/HW1/mycurl/mycurl.py "$U2" -s > "$SCRIPT_DIR/.p1.out"; RC1=$?
python homework/HW1/mycurl/mycurl2.py "$U2" -s > "$SCRIPT_DIR/.p2.out"; RC2=$?
if [ "$RC1" -eq "$RC2" ] && diff -q "$SCRIPT_DIR/.p1.out" "$SCRIPT_DIR/.p2.out" >/dev/null; then ok "兩支 body 輸出完全一致 (RC=$RC1)"; else bad "兩支 body 輸出不一致 (RC=$RC1/$RC2)"; fi
python homework/HW1/mycurl/mycurl.py "$U2" -i -s | grep -v "^Date:" > "$SCRIPT_DIR/.h1.out"
python homework/HW1/mycurl/mycurl2.py "$U2" -i -s | grep -v "^Date:" > "$SCRIPT_DIR/.h2.out"
if diff -q "$SCRIPT_DIR/.h1.out" "$SCRIPT_DIR/.h2.out" >/dev/null; then ok "兩支 -i 標頭一致 (排除 Date)"; else bad "兩支 -i 標頭不一致"; fi
rm -f "$SCRIPT_DIR/.p1.out" "$SCRIPT_DIR/.p2.out" "$SCRIPT_DIR/.h1.out" "$SCRIPT_DIR/.h2.out"

step 8 "mycurl2 --html-out 網頁報告"
if python homework/HW1/mycurl/mycurl2.py "$U2" -s --html-out "$SCRIPT_DIR/.report.html" >/dev/null; then
  if grep -q "HTTP 200" "$SCRIPT_DIR/.report.html" && grep -q "類似 curl" "$SCRIPT_DIR/.report.html"; then ok "--html-out 報告正確 (含狀態與內容)"; else bad "--html-out 報告缺關鍵內容"; fi
else
  bad "--html-out 執行失敗"
fi
rm -f "$SCRIPT_DIR/.report.html"
kill "$SRV2" 2>/dev/null
wait "$SRV2" 2>/dev/null

step 9 "mycurl2 --serve 本機網頁介面 (用 mycurl.py 反查它)"
PORT3=18767
python -m http.server "$PORT2" --directory "$ROOT" >/dev/null 2>&1 &
SRV3=$!
python homework/HW1/mycurl/mycurl2.py --serve "$PORT3" >/dev/null 2>&1 &
WEB=$!
sleep 2
if python homework/HW1/mycurl/mycurl.py "http://127.0.0.1:$PORT3/" -s -o "$SCRIPT_DIR/.form.html" && grep -q "<form" "$SCRIPT_DIR/.form.html"; then ok "--serve 首頁有表單"; else bad "--serve 首頁異常"; fi
ENC=$(python -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$U2")
if python homework/HW1/mycurl/mycurl.py "http://127.0.0.1:$PORT3/fetch?url=$ENC&method=GET&follow=on" -s -o "$SCRIPT_DIR/.fetch.html" && grep -q "HTTP 200" "$SCRIPT_DIR/.fetch.html" && grep -q "類似 curl" "$SCRIPT_DIR/.fetch.html"; then ok "--serve 代發請求並回網頁"; else bad "--serve 代發請求異常"; fi
rm -f "$SCRIPT_DIR/.form.html" "$SCRIPT_DIR/.fetch.html"
kill "$WEB" "$SRV3" 2>/dev/null
wait 2>/dev/null

echo "------------------------------"
echo "結果: PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
  exit 0
else
  echo "SOME CHECKS FAILED"
  exit 1
fi
