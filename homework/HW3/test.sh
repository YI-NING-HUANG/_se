#!/usr/bin/env bash
# 專案根目錄的一鍵入口，實際測試與報告都在 tast.sh/ 資料夾。
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SCRIPT_DIR/tast.sh/test.sh" "$@"
