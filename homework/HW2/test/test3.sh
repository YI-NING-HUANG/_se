#!/usr/bin/env bash
# HW2 test/test3.sh = app3 (v1.2 老師登分/管理員開課) 一鍵檢測
# 對應: homework/HW2/app3/ (= app2 + 登分開課，含回歸)
# 用法:
#   bash homework/HW2/test/test3.sh
# 結果寫入: homework/HW2/test/test-report3.txt
set -u
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT" || exit 1

bash homework/HW2/app3/test.sh 2>&1 | tee homework/HW2/test/test-report3.txt
