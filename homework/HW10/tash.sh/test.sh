#!/usr/bin/env bash
set -u
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT" || exit 1

REPORT="$SCRIPT_DIR/test-report.txt"
ARTIFACTS="$SCRIPT_DIR/artifacts"
UNIT_LOG="$ARTIFACTS/unittest.log"
HELP_LOG="$ARTIFACTS/help.log"
RUN_JSON="$ARTIFACTS/run.json"
COMPARE_JSON="$ARTIFACTS/compare.json"
OPTIMIZE_JSON="$ARTIFACTS/optimize.json"
DEMO_LOG="$ARTIFACTS/demo.log"
BUILD_LOG="$ARTIFACTS/build.log"
TWINE_LOG="$ARTIFACTS/twine.log"
WHEEL_LOG="$ARTIFACTS/wheel-install.log"
WHEEL_RUN="$ARTIFACTS/wheel-run.json"
WHEEL_ERR="$ARTIFACTS/wheel-run.err"
WHEEL_SITE="$ARTIFACTS/wheel-site"
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

native() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$1"
  else
    printf '%s' "$1"
  fi
}

pick_python() {
  if [ -n "${PYTHON:-}" ]; then
    printf '%s' "$PYTHON"
  elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
    printf '%s' "$ROOT/.venv/Scripts/python.exe"
  elif [ -x "$ROOT/.venv/Scripts/python" ]; then
    printf '%s' "$ROOT/.venv/Scripts/python"
  elif [ -x "$ROOT/.venv/bin/python" ]; then
    printf '%s' "$ROOT/.venv/bin/python"
  else
    command -v python || command -v python3
  fi
}

PYTHON_BIN="$(pick_python)"

main() {
  echo "cafeteria-sim tash.sh 測試"
  echo "日期: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "專案: $ROOT"
  echo "Python: $PYTHON_BIN"

  rm -rf "$ARTIFACTS"
  mkdir -p "$ARTIFACTS"

  section 1 "Python、依賴與編譯"
  if "$PYTHON_BIN" --version; then
    pass "Python 可執行"
  else
    fail "Python 不可執行"
  fi
  if "$PYTHON_BIN" -c "import simpy; print('simpy', simpy.__version__)"; then
    pass "SimPy 可用"
  else
    fail "SimPy 未安裝（請執行 pip install -e .[dev]）"
  fi
  if "$PYTHON_BIN" -c "import cafeteria_sim; print('cafeteria-sim', cafeteria_sim.__version__)"; then
    pass "套件可匯入"
  else
    fail "套件無法匯入"
  fi
  if "$PYTHON_BIN" -m compileall -q cafeteria_sim tests examples; then
    pass "cafeteria_sim/tests/examples 編譯通過"
  else
    fail "Python 編譯失敗"
  fi

  section 2 "單元測試"
  if "$PYTHON_BIN" -m unittest discover -s tests -v >"$UNIT_LOG" 2>&1; then
    cat "$UNIT_LOG"
    RAN="$(grep -o 'Ran [0-9][0-9]* tests' "$UNIT_LOG" | tail -1)"
    pass "單元測試全過（${RAN:-unittest OK}）"
  else
    cat "$UNIT_LOG"
    fail "單元測試失敗"
  fi

  section 3 "CLI 黑箱測試"
  if "$PYTHON_BIN" -m cafeteria_sim --help >"$HELP_LOG" 2>&1; then
    pass "python -m cafeteria_sim --help"
  else
    cat "$HELP_LOG"
    fail "python -m cafeteria_sim --help"
  fi

  if "$PYTHON_BIN" -m cafeteria_sim run \
    --arrival-rate 90 --duration 45 --warmup 5 \
    --order-windows 3 --order-mean 40 \
    --pickup-mode shared --pickup-servers 2 --pickup-mean 20 \
    --seed 11 --replications 2 --json >"$RUN_JSON" 2>"$ARTIFACTS/run.err"; then
    if "$PYTHON_BIN" - "$(native "$RUN_JSON")" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
metrics = data["metrics"]
assert data["replications"] == 2
assert metrics["served"] > 0
assert metrics["departures"] > 0
assert metrics["total_wait_p95_s"] >= metrics["total_wait_mean_s"] >= 0
print(
    "run: arrivals={:.0f} served={:.0f} mean_wait={:.1f}s p95={:.1f}s".format(
        metrics["arrivals"],
        metrics["served"],
        metrics["total_wait_mean_s"],
        metrics["total_wait_p95_s"],
    )
)
PY
    then
      pass "run --json（2 次模擬）"
    else
      fail "run JSON 內容驗證失敗"
    fi
  else
    cat "$ARTIFACTS/run.err"
    fail "run 指令執行失敗"
  fi

  if "$PYTHON_BIN" -m cafeteria_sim compare \
    --arrival-rate 90 --duration 45 --warmup 5 \
    --order-windows 2 --order-mean 40 --pickup-mode none \
    --windows 1,2,3 --replications 2 --json >"$COMPARE_JSON" 2>"$ARTIFACTS/compare.err"; then
    if "$PYTHON_BIN" - "$(native "$COMPARE_JSON")" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["replications"] == 2
assert len(data["scenarios"]) == 3
windows = [scenario["config"]["order_windows"] for scenario in data["scenarios"]]
assert windows == [1, 2, 3]
for scenario in data["scenarios"]:
    assert "total_wait_mean_s" in scenario["metrics"]
print("compare: windows={} mean_waits={}".format(
    windows,
    [round(scenario["metrics"]["total_wait_mean_s"], 1) for scenario in data["scenarios"]],
))
PY
    then
      pass "compare --json（1,2,3 窗口）"
    else
      fail "compare JSON 內容驗證失敗"
    fi
  else
    cat "$ARTIFACTS/compare.err"
    fail "compare 指令執行失敗"
  fi

  if "$PYTHON_BIN" -m cafeteria_sim optimize \
    --arrival-rate 60 --duration 30 --warmup 0 \
    --order-windows 1 --order-mean 30 --pickup-mode none \
    --max-order-windows 3 --target-mean-wait 300 \
    --order-cost 100 --pickup-cost 50 --replications 1 \
    --json >"$OPTIMIZE_JSON" 2>"$ARTIFACTS/optimize.err"; then
    if "$PYTHON_BIN" - "$(native "$OPTIMIZE_JSON")" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
best = data["best"]
assert best is not None
assert best["order_windows"] >= 1
assert best["hourly_cost"] > 0
assert best["metrics"]["total_wait_mean_s"] <= 300
print(
    "optimize: windows={} pickup={} cost={:.0f}/h mean_wait={:.1f}s".format(
        best["order_windows"],
        best["pickup_servers"],
        best["hourly_cost"],
        best["metrics"]["total_wait_mean_s"],
    )
)
PY
    then
      pass "optimize --json（最低成本配置）"
    else
      fail "optimize JSON 內容驗證失敗"
    fi
  else
    cat "$ARTIFACTS/optimize.err"
    fail "optimize 指令執行失敗"
  fi

  if "$PYTHON_BIN" -m cafeteria_sim demo >"$DEMO_LOG" 2>&1; then
    tail -n 20 "$DEMO_LOG"
    if grep -q "完成：套件已可執行" "$DEMO_LOG"; then
      pass "demo（情境比較 + 人力最佳化）"
    else
      fail "demo 輸出缺少完成訊息"
    fi
  else
    cat "$DEMO_LOG"
    fail "demo 執行失敗"
  fi

  section 4 "建置、twine 檢查與 wheel 安裝"
  rm -rf "$ROOT/dist" "$ROOT/build" "$ROOT/cafeteria_sim.egg-info"
  if "$PYTHON_BIN" -m build >"$BUILD_LOG" 2>&1; then
    WHEEL_COUNT="$(find "$ROOT/dist" -maxdepth 1 -name '*.whl' | wc -l | tr -d ' ')"
    SDIST_COUNT="$(find "$ROOT/dist" -maxdepth 1 -name '*.tar.gz' | wc -l | tr -d ' ')"
    if [ "$WHEEL_COUNT" -ge 1 ] && [ "$SDIST_COUNT" -ge 1 ]; then
      pass "python -m build（wheel=$WHEEL_COUNT, sdist=$SDIST_COUNT）"
    else
      fail "build 產物不完整（wheel=$WHEEL_COUNT, sdist=$SDIST_COUNT）"
    fi
  else
    cat "$BUILD_LOG"
    fail "python -m build 失敗"
  fi

  if "$PYTHON_BIN" -m twine check "$ROOT"/dist/* >"$TWINE_LOG" 2>&1; then
    cat "$TWINE_LOG"
    pass "twine check"
  else
    cat "$TWINE_LOG"
    fail "twine check 失敗"
  fi

  WHEEL="$(find "$ROOT/dist" -maxdepth 1 -name '*.whl' -print -quit 2>/dev/null || true)"
  if [ -n "$WHEEL" ]; then
    rm -rf "$WHEEL_SITE"
    if "$PYTHON_BIN" -m pip install --no-deps --target "$(native "$WHEEL_SITE")" "$(native "$WHEEL")" >"$WHEEL_LOG" 2>&1; then
      IMPORTED="$(cd "$ARTIFACTS" && PYTHONPATH="$(native "$WHEEL_SITE")" "$PYTHON_BIN" -c 'import cafeteria_sim; print(cafeteria_sim.__file__)')"
      case "$IMPORTED" in
        *wheel-site*)
          pass "wheel 匯入路徑正確"
          ;;
        *)
          fail "wheel 匯入到錯誤路徑：$IMPORTED"
          ;;
      esac

      if (cd "$ARTIFACTS" && PYTHONPATH="$(native "$WHEEL_SITE")" "$PYTHON_BIN" -m cafeteria_sim run \
        --arrival-rate 60 --duration 20 --warmup 0 \
        --order-windows 2 --order-mean 20 --pickup-mode none \
        --seed 3 --json >"$WHEEL_RUN" 2>"$WHEEL_ERR"); then
        if "$PYTHON_BIN" - "$(native "$WHEEL_RUN")" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data["metrics"]["served"] > 0
assert "total_wait_p95_s" in data["metrics"]
print("wheel CLI: served={:.0f}".format(data["metrics"]["served"]))
PY
        then
          pass "wheel 安裝後 CLI 可執行"
        else
          fail "wheel CLI JSON 驗證失敗"
        fi
      else
        cat "$WHEEL_ERR"
        fail "wheel 安裝後 CLI 執行失敗"
      fi
    else
      cat "$WHEEL_LOG"
      fail "wheel 安裝到暫存目錄失敗"
    fi
  else
    fail "找不到 wheel，跳過安裝測試"
  fi

  rm -rf "$WHEEL_SITE"

  echo
  echo "----------------------------------------"
  echo "結果: PASS=$PASS FAIL=$FAIL"
  if [ "$FAIL" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    echo "測試報告: $REPORT"
    echo "建置產物: $ROOT/dist"
    return 0
  fi
  echo "SOME CHECKS FAILED"
  echo "測試報告: $REPORT"
  return 1
}

main 2>&1 | tee "$REPORT"
exit "${PIPESTATUS[0]}"
