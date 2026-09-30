#!/usr/bin/env bash
# HW2 test/test-all.sh: 一次跑完 v1.0 + v1.1 + v1.2
# 用法:
#   bash homework/HW2/test/test-all.sh
set -u
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT" || exit 1

FAIL=0
bash homework/HW2/test/test.sh || FAIL=1
echo ""
bash homework/HW2/test/test2.sh || FAIL=1
echo ""
bash homework/HW2/test/test3.sh || FAIL=1
echo ""
echo "=============================="
if [ "$FAIL" -eq 0 ]; then
  echo "HW2 ALL VERSIONS PASSED (v1.0 + v1.1 + v1.2)"
else
  echo "HW2 SOME VERSION FAILED"
fi
exit "$FAIL"
