#!/usr/bin/env bash
# HW2 test/test2.sh = app2 (v1.1 成績查詢/GPA) 一鍵檢測
# 對應: homework/HW02/app2/ (= app1 + 成績，含 app1 回歸)
# 用法:
#   bash homework/HW02/test/test2.sh
# 結果寫入: homework/HW02/test/test-report2.txt
set -u
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT" || exit 1

bash homework/HW02/app2/test.sh 2>&1 | tee homework/HW02/test/test-report2.txt
