#!/usr/bin/env bash
# ForumKeep 一鍵測試：單元測試 + CLI + 本機範例論壇端到端
# 用法：bash tast.sh/test.sh
# 報告：tast.sh/test-report.txt
# 展示：tast.sh/artifacts/demo/site/index.html
set -u
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT" || exit 1

REPORT="$SCRIPT_DIR/test-report.txt"
ARTIFACTS="$SCRIPT_DIR/artifacts"
DEMO="$ARTIFACTS/demo"
SERVER_LOG="$ARTIFACTS/server.log"
SERVER_PID=""
PASS=0
FAIL=0

pass() {
  PASS=$((PASS + 1))
  printf 'PASS: %s\n' "$*"
}

fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL: %s\n' "$*"
}

section() {
  printf '\n=== [%s] %s ===\n' "$1" "$2"
}

cleanup() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

main() {
  echo "ForumKeep 測試"
  echo "日期: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "Python: $(python --version 2>&1)"
  echo "專案: $ROOT"

  rm -rf "$ARTIFACTS"
  mkdir -p "$ARTIFACTS"

  section 1 "Python 與編譯"
  if python --version; then
    pass "Python 可執行"
  else
    fail "Python 不可執行"
  fi
  if python -m compileall -q forumkeep tests; then
    pass "forumkeep/tests 編譯通過"
  else
    fail "forumkeep/tests 編譯失敗"
  fi

  section 2 "單元測試"
  UNIT_LOG="$ARTIFACTS/unittest.log"
  if python -m unittest discover -s tests -v >"$UNIT_LOG" 2>&1; then
    cat "$UNIT_LOG"
    RAN="$(grep -o 'Ran [0-9][0-9]* tests' "$UNIT_LOG" | tail -1)"
    pass "單元測試全過（${RAN:-unittest OK}）"
  else
    cat "$UNIT_LOG"
    fail "單元測試失敗"
  fi

  section 3 "CLI 基本檢查"
  VERSION="$(python -m forumkeep --version 2>&1)"
  echo "$VERSION"
  case "$VERSION" in
    ForumKeep*) pass "python -m forumkeep --version" ;;
    *) fail "version 輸出格式不正確" ;;
  esac
  if python -m forumkeep --help >/dev/null 2>&1; then
    pass "python -m forumkeep --help"
  else
    fail "python -m forumkeep --help"
  fi

  section 4 "端到端：本機範例論壇"
  PORT="$(python - <<'PY'
import socket
sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
)"
  python -m http.server "$PORT" --bind 127.0.0.1 \
    --directory examples/mini_forum >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!

  READY=0
  for _ in $(seq 1 50); do
    if python - "$PORT" <<'PY'
import sys
import urllib.request
try:
    urllib.request.urlopen(
        f"http://127.0.0.1:{sys.argv[1]}/robots.txt", timeout=1
    ).read(1)
except Exception:
    raise SystemExit(1)
PY
    then
      READY=1
      break
    fi
    sleep 0.1
  done

  if [ "$READY" -eq 1 ]; then
    pass "測試伺服器啟動（127.0.0.1:$PORT）"
  else
    fail "測試伺服器啟動失敗"
    cat "$SERVER_LOG"
  fi

  if [ "$READY" -eq 1 ]; then
    if python -m forumkeep run \
      --url "http://127.0.0.1:$PORT/" \
      --out "$DEMO" --delay 0 --retries 1 --max-pages 50; then
      pass "forumkeep run（crawl + download + build）"
    else
      fail "forumkeep run"
    fi

    if python -m forumkeep status --out "$DEMO"; then
      pass "forumkeep status"
    else
      fail "forumkeep status"
    fi

    if python -m forumkeep verify --out "$DEMO"; then
      pass "forumkeep verify（雜湊與檔案檢查）"
    else
      fail "forumkeep verify"
    fi

    if python - "$DEMO" "$PORT" <<'PY'
import sqlite3
import sys
from pathlib import Path

from forumkeep.build import page_site_path

archive = Path(sys.argv[1])
port = sys.argv[2]
site = archive / "site"
db = sqlite3.connect(archive / "forumkeep.sqlite3")
pages = db.execute("SELECT COUNT(*) FROM pages WHERE status='done'").fetchone()[0]
assets = db.execute("SELECT COUNT(*) FROM assets WHERE status='done'").fetchone()[0]
private_pages = db.execute(
    "SELECT COUNT(*) FROM pages WHERE url LIKE '%/private/%'"
).fetchone()[0]
problems = []
if pages < 5:
    problems.append(f"done pages={pages}")
if assets < 5:
    problems.append(f"done assets={assets}")
if private_pages:
    problems.append(f"private pages archived={private_pages}")
if not (site / "index.html").exists():
    problems.append("site/index.html missing")
if not (site / "search.html").exists():
    problems.append("site/search.html missing")
if not (site / "assets.html").exists():
    problems.append("site/assets.html missing")
if not (site / "manifest.json").exists():
    problems.append("site/manifest.json missing")

home = site / page_site_path(f"http://127.0.0.1:{port}/")
if not home.exists():
    problems.append(f"built home missing: {home}")
else:
    home_html = home.read_text(encoding="utf-8")
    private_url = f"http://127.0.0.1:{port}/private/secret.html"
    if private_url not in home_html:
        problems.append("unarchived private link was not kept as absolute URL")
    if "<script" in home_html.lower():
        problems.append("script tag survived sanitization")

for path in db.execute(
    "SELECT local_path FROM assets WHERE status='done' AND local_path IS NOT NULL"
):
    if not (archive / path[0]).exists():
        problems.append(f"missing blob: {path[0]}")

if problems:
    print("E2E PROBLEMS:")
    for problem in problems:
        print(f"  - {problem}")
    raise SystemExit(1)
print(f"頁面={pages} 素材={assets} private_pages={private_pages}")
print(f"離線首頁: {site / 'index.html'}")
print(f"封存首頁: {home}")
PY
    then
      pass "離線站內容與封存完整性"
    else
      fail "離線站內容與封存完整性"
    fi
  fi

  echo
  echo "----------------------------------------"
  echo "結果: PASS=$PASS FAIL=$FAIL"
  if [ "$FAIL" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    echo "測試報告: $REPORT"
    echo "展示站台: $DEMO/site/index.html"
    return 0
  fi
  echo "SOME CHECKS FAILED"
  echo "測試報告: $REPORT"
  return 1
}

main 2>&1 | tee "$REPORT"
exit "${PIPESTATUS[0]}"
