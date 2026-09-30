#!/usr/bin/env bash
# HW2 test/test.sh = app1 (v1.0 主要功能) 一鍵檢測
# 對應: homework/HW2/app1/ (選課核心)
# 用法:
#   bash homework/HW2/test/test.sh
# 結果寫入: homework/HW2/test/test-report.txt
set -u
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT" || exit 1

bash homework/HW2/app1/test.sh 2>&1 | tee homework/HW2/test/test-report.txt
