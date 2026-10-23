#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.." || exit 1

PYTHON_BIN="${PYTHON:-python}"
REPORT="tests/test-report.txt"
E2E_DIR="tests/e2e"
status=0

{
  echo "DINO RUN test report"
  date
  "$PYTHON_BIN" --version
  if command -v node >/dev/null 2>&1; then
    node --version
  else
    echo "node: not found"
  fi
  echo
} > "$REPORT"

section() {
  echo "" | tee -a "$REPORT"
  echo "===== $* =====" | tee -a "$REPORT"
}

run_python_suite() {
  local label="$1"
  local directory="$2"
  section "$label"
  "$PYTHON_BIN" -m unittest discover -s "$directory" -t . -v 2>&1 | tee -a "$REPORT"
  local code=${PIPESTATUS[0]}
  if [ "$code" -ne 0 ]; then
    status=1
  fi
}

run_python_suite "Unit tests (server core: validation + SQLite)" "tests/unit"
run_python_suite "System tests (HTTP server + Web API)" "tests/system"

section "JavaScript syntax"
if command -v node >/dev/null 2>&1; then
  if node --check static/game.js >> "$REPORT" 2>&1 && node --check static/sw.js >> "$REPORT" 2>&1; then
    echo "JS syntax OK" | tee -a "$REPORT"
  else
    echo "JS syntax FAILED" | tee -a "$REPORT"
    status=1
  fi
else
  echo "node not found; JS syntax check skipped" | tee -a "$REPORT"
  status=1
fi

section "E2E tests (Playwright + headless Chrome)"
if command -v node >/dev/null 2>&1; then
  if [ ! -f "$E2E_DIR/node_modules/@playwright/test/package.json" ]; then
    echo "Playwright dependencies not found; running npm install..." | tee -a "$REPORT"
    (
      cd "$E2E_DIR" || exit 1
      env -u npm_config_allow_scripts npm install --no-audit --no-fund
    ) 2>&1 | tee -a "$REPORT"
    if [ "${PIPESTATUS[0]}" -ne 0 ]; then
      echo "Playwright dependency install FAILED" | tee -a "$REPORT"
      status=1
    fi
  fi

  if [ -f "$E2E_DIR/node_modules/@playwright/test/package.json" ]; then
    (
      cd "$E2E_DIR" || exit 1
      rm -rf .tmp test-results playwright-report blob-report
      ./node_modules/.bin/playwright test
    ) 2>&1 | tee -a "$REPORT"
    if [ "${PIPESTATUS[0]}" -ne 0 ]; then
      status=1
    fi
  else
    echo "E2E skipped: missing Playwright dependencies" | tee -a "$REPORT"
    status=1
  fi
else
  echo "E2E skipped: node not found" | tee -a "$REPORT"
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "ALL CHECKS PASSED" | tee -a "$REPORT"
else
  echo "SOME CHECKS FAILED" | tee -a "$REPORT"
fi

exit "$status"
