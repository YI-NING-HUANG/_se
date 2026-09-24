#!/usr/bin/env bash
# HW1 mycurl 一鍵檢測: 確認整個程式可以跑動
# 位置: homework/HW1/mycurl/test.sh (與 mycurl.py / mycurl2.py 同資料夾)
# 用法:
#   bash homework/HW1/mycurl/test.sh
#   bash homework/HW1/mycurl/test.sh 2>&1 | tee homework/HW1/mycurl/test-report.log
set -u

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

step 3 "mycurl2.py 基本指令"
if python homework/HW1/mycurl/mycurl2.py --version; then ok "mycurl2.py --version"; else bad "mycurl2.py --version"; fi
if python homework/HW1/mycurl/mycurl2.py --help >/dev/null; then ok "mycurl2.py --help"; else bad "mycurl2.py --help"; fi

step 4 "單元測試 (本機 http.server, 不需外網)"
if python -m unittest discover -s homework/HW1/mycurl/tests -v; then ok "unittest 全過"; else bad "unittest 有失敗"; fi

step 5 "mycurl2.py 產生 index.html"
if python homework/HW1/mycurl/mycurl2.py -o homework/HW1/mycurl/index.html; then ok "index.html 產生成功"; else bad "index.html 產生失敗"; fi
if grep -q "mycurl2.py" homework/HW1/mycurl/index.html && grep -q "NoRedirect" homework/HW1/mycurl/index.html; then ok "index.html 內容正確 (含 mycurl2 與原始碼)"; else bad "index.html 內容缺關鍵字"; fi

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

echo "------------------------------"
echo "結果: PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
  exit 0
else
  echo "SOME CHECKS FAILED"
  exit 1
fi
