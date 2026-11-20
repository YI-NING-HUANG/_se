# HW11 — 套件發佈（PyPI）與 AI 使用說明

延續 HW10 的 `cafeteria-sim`，本作業把套件正式發佈到 PyPI，
並在套件頁面加入給 AI 助手使用的說明。

欄位 | 內容
-----|---------
套件名稱 | [`cafeteria-sim`](https://pypi.org/project/cafeteria-sim/)
Python 模組 | `cafeteria_sim`
目前版本 | 0.1.1
PyPI 專案 | <https://pypi.org/project/cafeteria-sim/>
原始碼 | [homework/HW10](https://github.com/yi-ning-huang/_se/tree/main/homework/HW10)
授權 | MIT

## 1. 完成內容

- 以 `pyproject.toml`（setuptools）建置 sdist 與 wheel。
- 以 `twine` 上傳至 PyPI，版本 `0.1.0` 與 `0.1.1`。
- `twine check` 通過，README 可正確顯示於 PyPI 專案頁。
- 使用 **project-scoped API token**（僅限 `cafeteria-sim`），token 不寫入 repo。
- 在 README 新增「AI 使用說明」章節，隨套件描述同步顯示在 PyPI 頁面。

## 2. 安裝與快速驗證

```bash
pip install cafeteria-sim
cafeteria-sim demo
```

以 Python API 執行：

```python
from cafeteria_sim import SimulationConfig, run_simulation

config = SimulationConfig(
    arrival_rate_per_hour=120,
    duration_minutes=120,
    warmup_minutes=10,
    order_windows=3,
    order_mean_s=75,
    pickup_mode="shared",
    pickup_servers=2,
    pickup_mean_s=45,
    seed=42,
)

result = run_simulation(config)
print(result.metrics["total_wait_mean_s"])
print(result.metrics["total_wait_p95_s"])
```

## 3. AI 使用說明

PyPI 頁面的「AI 使用說明」章節提供：

- 套件定位與限制（DES 模擬，不是 M/M/c 解析解）。
- 參數與單位對照表（人/小時、分鐘、秒）。
- 建議的 AI 工作流程：基準情境 → `compare_windows` → `optimize_staffing`。
- 可直接貼給 AI 的 prompt 範例。
- AI 回答時應遵守的指標定義與注意事項。
- 驗證 AI 產生程式的方法。

完整內容請見：

- PyPI：<https://pypi.org/project/cafeteria-sim/>
- 原始碼 README：[HW10/README.md 第 12 節](https://github.com/yi-ning-huang/_se/tree/main/homework/HW10#12-ai-使用說明給-ai-助手與-llm)

摘要：

```text
請使用 Python 套件 cafeteria-sim 回答我的學餐人力問題。
情境：每小時 120 人到達、3 個點餐窗口、平均點餐 75 秒、
共用 2 個取餐檯、平均取餐 45 秒，模擬 120 分鐘、暖機 10 分鐘。
請先跑 run_simulation，再用 compare_windows 比較相鄰窗口數，
最後用 optimize_staffing 在等候目標下找最低成本配置。
附上完整參數、seed 與 replications，讓結果可重現。
```

## 4. 發佈流程

```bash
cd homework/HW10

python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"

python -m build
python -m twine check dist/*

# token 只放在環境變數，不寫進 repo
TWINE_USERNAME=__token__ \
TWINE_PASSWORD=pypi-你的-project-scoped-token \
python -m twine upload dist/*
```

PowerShell：

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "pypi-你的-project-scoped-token"
python -m twine upload dist/*
```

同一個版本不能重複上傳；更新內容時先調升 `pyproject.toml` 的 `version`。

## 5. 驗證

```bash
cd homework/HW10
.venv/Scripts/python -m unittest discover -s tests -v
.venv/Scripts/python -m build
.venv/Scripts/python -m twine check dist/*
```

- 35 個 unittest 通過。
- `twine check` 對 wheel 與 sdist 皆為 `PASSED`。
- 從 PyPI 安裝後可執行 `cafeteria-sim demo`。
