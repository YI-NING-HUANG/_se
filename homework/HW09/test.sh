#!/usr/bin/env bash
set -u -o pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8788}"
BASE_URL="http://127.0.0.1:${PORT}"
REPORT="tests/test-report.txt"
DEV_LOG=".wrangler/dev-test.log"
PASS_STEPS=0
FAIL_STEPS=0
DEV_PID=""

mkdir -p .wrangler tests
: > "$REPORT"

log() {
  printf '%s\n' "$*" | tee -a "$REPORT"
}

cleanup() {
  if [ -n "$DEV_PID" ]; then
    kill "$DEV_PID" 2>/dev/null || true
    if command -v taskkill >/dev/null 2>&1; then
      taskkill //F //T //PID "$DEV_PID" >/dev/null 2>&1 || true
    fi
    DEV_PID=""
  fi
}
trap cleanup EXIT INT TERM

step() {
  local name="$1"
  shift
  log ""
  log "===== $name ====="
  if "$@" 2>&1 | tee -a "$REPORT"; then
    log "PASS  $name"
    PASS_STEPS=$((PASS_STEPS + 1))
    return 0
  fi
  log "FAIL  $name"
  FAIL_STEPS=$((FAIL_STEPS + 1))
  return 1
}

log "HW9 DINO RUN — Cloudflare Workers + D1 測試報告"
log "時間：$(date -Iseconds 2>/dev/null || date)"
log "Node：$(node --version)"
log "Wrangler：$(npx --yes wrangler --version 2>&1 | tail -n 1)"

step "JavaScript 語法檢查" bash -c \
  "node --check src/index.js && node --check public/game.js && node --check public/sw.js"

step "套用 D1 migration（local）" \
  npx --yes wrangler d1 migrations apply DB --local

step "清空測試資料庫" \
  npx --yes wrangler d1 execute DB --local --command "DELETE FROM scores;"

step "Wrangler 打包驗證（dry-run）" \
  npx --yes wrangler deploy --dry-run --outdir .wrangler/dry-run

step "產生單檔 HTML（standalone）" bash -c \
  "node scripts/build-standalone.mjs && test -s index.html && grep -q 'DINO_API_BASE' index.html && ! grep -q 'src=\"./game.js\"' index.html"

log ""
log "===== 啟動 wrangler dev ====="
npx --yes wrangler dev --port "$PORT" --ip 127.0.0.1 >"$DEV_LOG" 2>&1 &
DEV_PID=$!

READY=0
for _ in $(seq 1 120); do
  if node -e "fetch('$BASE_URL/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))" 2>/dev/null; then
    READY=1
    break
  fi
  sleep 0.5
done

if [ "$READY" -eq 1 ]; then
  log "dev server 已啟動：$BASE_URL"
  step "單元測試（validation）" \
    node --test --test-reporter=tap tests/unit/validation.test.js
  step "API 系統測試（Cloudflare Workers + D1）" \
    node --test --test-reporter=tap tests/api/api.test.js
else
  log "dev server 啟動失敗，以下為 wrangler dev 輸出："
  sed -n '1,160p' "$DEV_LOG" | tee -a "$REPORT"
  FAIL_STEPS=$((FAIL_STEPS + 1))
fi

TESTS=$(grep -E "^# tests " "$REPORT" | awk '{sum += $3} END {print sum + 0}')
PASSED=$(grep -E "^# pass " "$REPORT" | awk '{sum += $3} END {print sum + 0}')
FAILED=$(grep -E "^# fail " "$REPORT" | awk '{sum += $3} END {print sum + 0}')

log ""
log "===== 測試總結 ====="
log "測試案例：${TESTS}（PASS=${PASSED} FAIL=${FAILED}）"
log "測試步驟：PASS=${PASS_STEPS} FAIL=${FAIL_STEPS}"

if [ "$FAIL_STEPS" -eq 0 ] && [ "$TESTS" -gt 0 ] && [ "$FAILED" -eq 0 ]; then
  log "ALL CHECKS PASSED"
  exit 0
fi

log "SOME CHECKS FAILED"
exit 1
