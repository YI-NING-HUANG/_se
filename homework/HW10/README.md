# cafeteria-sim

用 **SimPy** 建立的學餐排隊 **離散事件模擬（Discrete Event Simulation, DES）** 套件。
它模擬尖峰時段的多個點餐窗口、共用或分開的取餐動線、顧客不耐煩離開，
並用模擬結果比較「多開一個窗口」能減少多少等候時間，
最後在等候目標下找出最低成本的人力配置。

- 套件名稱：`cafeteria-sim`
- Python 模組：`cafeteria_sim`
- 執行環境：Python 3.10+
- 執行期依賴：`simpy>=4.1,<5`
- 授權：MIT

## 1. 主題與動機

學校餐廳在中午尖峰常同時出現：

- 多個點餐窗口，每個窗口排队速度不同（菜色、刷卡、找零）。
- 點完餐後可能有**共用取餐區**，也可能每個窗口有**自己的取餐動線**。
- 顧客看到隊伍太長會直接離開（balking），排太久也會放棄（reneging）。
- 窗口與取餐人力是成本，等候時間是體驗，兩者需要取捨。

當系統有多個服務站、不同動線與放棄行為時，單一 M/M/c 公式很難完整描述。
因此本套件採用 DES：把每位顧客、每個窗口、每個取餐檯都建成 SimPy 資源，
逐步推進事件時間，最後統計等候時間、排隊長度、使用率與吞吐量。

這個套件對應課程「階段三：作業研究與排隊模擬」的主題，
並把課堂提到的兩個方向都做成可執行的工具：

| 課堂方向 | 本套件的做法 |
|---|---|
| SimPy 排隊模擬 | 核心引擎，支援多窗口、共用／獨立取餐線、balk、renege、暖機 |
| PuLP／SciPy 最佳化 | 以**模擬式整數搜尋**在有限人力組合中找最低成本方案；不需要把非線性的等候限制硬塞進線性規劃 |

## 2. 安裝

從 PyPI 安裝：

```bash
pip install cafeteria-sim
```

專案頁面：<https://pypi.org/project/cafeteria-sim/>

從原始碼安裝：

```bash
git clone https://github.com/yi-ning-huang/_se.git
cd _se/homework/HW10
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"   # macOS / Linux
```

## 3. 快速驗證

```bash
cafeteria-sim demo
```

`demo` 會跑一個內建的午餐尖峰情境：每小時 120 人到達、3 個點餐窗口、
點餐平均 75 秒、共用 2 個取餐檯、取餐平均 45 秒，模擬 2 小時並暖機 10 分鐘。
它會同時示範「加開窗口」與「最低成本人力」兩個功能。

執行完整測試（單元測試＋CLI＋建置＋wheel 安裝）：

```bash
bash tash.sh/test.sh
# 或在 HW10 根目錄
bash test.sh
```

報告會寫到 `tash.sh/test-report.txt`，詳細輸出在 `tash.sh/artifacts/`。
目前 `tash.sh` 的結果為 **PASS=14 FAIL=0**，其中包含 **35 個 unittest**，
涵蓋設定驗證、四種服務時間分布、balk／renege、暖機排除、重現性、
共用／獨立取餐、情境比較、成本最佳化、JSON 輸出與 CLI 錯誤處理。

## 4. 命令列用法

### 4.1 單一情境

```bash
cafeteria-sim run \
  --arrival-rate 120 \
  --duration 120 \
  --warmup 10 \
  --order-windows 3 \
  --order-mean 75 \
  --pickup-mode shared \
  --pickup-servers 2 \
  --pickup-mean 45 \
  --seed 42
```

加上 `--replications 5 --json` 可以跑 5 次獨立模擬並輸出機器可讀的 JSON。

### 4.2 比較加開窗口

```bash
cafeteria-sim compare \
  --arrival-rate 120 \
  --order-mean 75 \
  --pickup-mode shared \
  --pickup-servers 2 \
  --pickup-mean 45 \
  --windows 1,2,3,4,5 \
  --replications 3
```

本範例的實際輸出（節錄）：

```text
 Win    Mean(s)     P95(s)    Done%   PerHour    Order%   Pickup%   MaxQ
------------------------------------------------------------------------
   1    5,727.5   10,074.0   100.0%      46.5    100.0%     28.4%       162
   2      775.9    1,844.6   100.0%      97.6     97.8%     60.3%        29
   3      165.3      444.0   100.0%     117.5     82.5%     72.3%         6
   4      109.6      351.4   100.0%     116.5     62.2%     71.2%         2
   5       89.7      303.8   100.0%     117.8     47.0%     73.1%         2
```

重點解讀：

- 只有 1 個窗口時，點餐容量約 48 人/小時，遠低於 120 人的到達率，
  排隊幾乎無上限，平均等候超過 1.5 小時。
- 3 個窗口時容量已足夠，平均總等候降到約 165 秒；
  但取餐區固定 2 人，取餐使用率約 72%，成為下一個瓶頸。
- 4、5 個窗口的邊際效益快速下降：等候變短，但點餐窗口使用率掉到 62%、47%。

### 4.3 最低成本人力配置

```bash
cafeteria-sim optimize \
  --arrival-rate 120 \
  --order-mean 75 \
  --pickup-mean 45 \
  --target-mean-wait 180 \
  --target-p95-wait 450 \
  --max-order-windows 6 \
  --max-pickup-servers 4 \
  --order-cost 150 \
  --pickup-cost 100 \
  --replications 3
```

實際輸出（節錄）：

```text
目標：平均總等候 <= 180 秒、P95 總等候 <= 450 秒
最佳方案：點餐窗口 3 個、取餐檯 2 個，成本 650 元/小時
  平均總等候 165.3 秒、P95 444.0 秒、完成率 100.0%

 Win  Pickup     Cost/h    Mean(s)     P95(s)    Done%
------------------------------------------------------
   3      2        650      165.3      444.0   100.0%
   4      2        800      109.6      351.4   100.0%
   3      4        850      101.3      355.6   100.0%
```

最佳解不是等候最短的方案，而是在**滿足等候目標**的前提下成本最低的方案。
若目標太嚴苛、超過搜尋上限，指令會回傳非零結束碼並列出等候最短的候選方案。

`--json` 可輸出所有候選方案與其完整指標，方便進一步畫圖或寫報告。

## 5. Python API

```python
from cafeteria_sim import SimulationConfig, compare_windows, run_simulation

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

for scenario in compare_windows(config, [2, 3, 4], replications=3):
    print(scenario.label, scenario.metrics["total_wait_mean_s"])
```

也可以直接使用最佳化：

```python
from cafeteria_sim import SimulationConfig, optimize_staffing

plan = optimize_staffing(
    SimulationConfig(arrival_rate_per_hour=120, order_mean_s=75, pickup_mean_s=45),
    max_order_windows=6,
    max_pickup_servers=4,
    order_window_cost=150,
    pickup_server_cost=100,
    target_mean_wait_s=180,
    target_p95_wait_s=450,
    replications=3,
)
print(plan.best.order_windows, plan.best.pickup_servers, plan.best.hourly_cost)
```

完整範例見 `examples/quickstart.py`。

## 6. 模型與指標

### 6.1 模型假設

- 顧客以 Poisson 過程到達（指數分布間隔），到達率以「人/小時」設定。
- 點餐與取餐服務時間可選：
  - `exponential`：指數分布，平均值為設定值。
  - `deterministic`：固定時間。
  - `uniform`：均勻分布於平均值的 0.5 到 1.5 倍。
  - `triangular`：三角分布，下限／眾數／上限為平均值的 0.5／1.0／1.5 倍。
- 點餐窗口：每個窗口 capacity 1，顧客加入最短的窗口隊伍。
- 取餐模式：
  - `shared`：所有窗口共用一個取餐區，取餐檯數量由 `pickup_servers` 決定。
  - `per_window`：每個點餐窗口有自己的一條取餐線，capacity 1。
  - `none`：點完餐就離開（用於只看點餐瓶頸）。
- 排隊上限：`max_order_queue`、`max_pickup_queue` 可模擬看到太長就離開（balk）。
- 耐心：`order_patience`、`pickup_patience` 可模擬排太久放棄（renege），
  耐心時間採指數分布。
- 暖機：`warmup` 分鐘內的顧客仍會影響系統狀態，但不列入統計，
  避免餐廳一開門空系統造成等候時間被低估。
- 每次模擬使用固定 seed；多次 replication 使用 `seed, seed+1, ...`。
- 情境比較對所有窗口數使用同一組 seeds（common random numbers），
  降低不同情境之間的隨機差異。

### 6.2 指標定義

| 指標 | 定義 |
|---|---|
| `arrivals` | 觀察期間內到達的顧客數 |
| `served` | 觀察期間內到達且最終完成點餐＋取餐的顧客數 |
| `departures` | 觀察期間內完成並離開的顧客數（用於吞吐量） |
| `abandoned` | 觀察期間內到達但未完成的顧客數 |
| `balked` / `balked_pickup` | 看到點餐／取餐隊伍太長而直接離開 |
| `reneged_order` / `reneged_pickup` | 排隊超過耐心而放棄 |
| `completion_rate` | `served / arrivals` |
| `throughput_per_hour` | 觀察期間內離開人數 ÷ 觀察時數 |
| `total_wait_*` | 點餐排隊＋取餐排隊時間（不含服務時間） |
| `system_time_*` | 從到達至離開的總時間（含服務時間） |
| `*_utilization` | 服務中時間 ÷（服務檯數 × 觀察時數） |
| `avg_*_queue` | 時間加權的平均排隊人數（含正在等待的人） |
| `max_*_queue` | 觀察期間內最大排隊人數 |
| `p95` | 最近秩百分位（nearest-rank） |

`run --json` 與 `compare --json` 會輸出所有指標，方便寫報告或畫圖。

## 7. 為什麼用模擬式最佳化，而不是直接丟給 PuLP？

課堂投影片提到可加入 PuLP／`SciPy.optimize` 做「最低成本排班」。
這個套件保留了成本最小化的目標，但採用**整數枚舉＋DES 評估**，原因是：

1. 等候時間對人力數量的關係是**非線性**的，而且有隨機性；
   直接寫成線性規劃會失真。
2. 點餐窗口與取餐檯是**整數**決策，且兩者會互相成為瓶頸。
3. `shared`／`per_window` 動線、balk、renege、非指數服務時間
   都不容易用單一 M/M/c 公式表示。
4. 本套件的搜尋空間很小（例如 6 個窗口 × 4 個取餐檯 = 24 個方案），
   對每個方案跑 DES 反而直接、可解釋，也能輸出所有候選方案。

如果未來要加入更大的排班問題（例如不同時段、不同技能、加班費），
可以再把線性規劃或混合整數規劃接到 `optimize_staffing` 的候選產生器，
用 DES 做最後驗證。

## 8. 驗證與打包

```bash
# 一鍵測試（單元測試、CLI、建置、twine check、wheel 安裝）
bash tash.sh/test.sh

# 只跑單元測試
python -m unittest discover -s tests -v

# 建置 sdist + wheel
python -m build

# 檢查套件中介資料與 README
python -m twine check dist/*

# 在乾淨環境安裝 wheel 並執行
python -m venv .venv-check

# Windows
.venv-check\Scripts\pip install dist\cafeteria_sim-0.1.1-py3-none-any.whl
.venv-check\Scripts\cafeteria-sim demo

# macOS / Linux
.venv-check/bin/pip install dist/cafeteria_sim-0.1.1-py3-none-any.whl
.venv-check/bin/cafeteria-sim demo
```

目前已驗證：

- `bash tash.sh/test.sh`：**PASS=14 FAIL=0**，報告在 `tash.sh/test-report.txt`。
- 35 個 unittest 全數通過。
- `python -m build` 成功產生 `cafeteria_sim-0.1.1.tar.gz` 與
  `cafeteria_sim-0.1.1-py3-none-any.whl`。
- `twine check` 通過。
- wheel 安裝到暫存目錄後可匯入，並可執行 `python -m cafeteria_sim run`。
- 在乾淨虛擬環境以 wheel 安裝後，`cafeteria-sim demo` 可正常執行。

## 9. 發布到公開套件庫

本套件以 PyPI 為公開套件庫。發布指令如下（token 請放在環境變數，不要寫進 repo）：

```bash
python -m build
python -m twine check dist/*

# 先上 TestPyPI 驗證
TWINE_USERNAME=__token__ \
TWINE_PASSWORD=pypi-你的-testpypi-token \
python -m twine upload --repository testpypi dist/*

# 確認 TestPyPI 可安裝後，再上正式 PyPI
TWINE_USERNAME=__token__ \
TWINE_PASSWORD=pypi-你的-pypi-token \
python -m twine upload dist/*
```

Windows PowerShell 版本：

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "pypi-你的-pypi-token"
python -m twine upload dist/*
```

發布後即可用 `pip install cafeteria-sim` 安裝，
專案頁面為 <https://pypi.org/project/cafeteria-sim/>。

## 10. 專案結構

```text
homework/HW10/
├── cafeteria_sim/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # run / compare / optimize / demo
│   ├── config.py           # 設定驗證與單位轉換
│   ├── distributions.py    # 四種服務時間分布
│   ├── metrics.py          # 百分位、排隊面積、最大重疊
│   ├── optimization.py     # 模擬式整數人力搜尋
│   ├── simulation.py       # SimPy 模型、顧客紀錄、統計
│   └── py.typed
├── examples/
│   └── quickstart.py
├── tests/
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_distributions.py
│   ├── test_metrics.py
│   ├── test_optimization.py
│   └── test_simulation.py
├── tash.sh/
│   ├── test.sh             # 一鍵測試入口
│   ├── test-report.txt     # 測試報告
│   ├── README.md
│   └── artifacts/          # unittest / CLI / build / wheel 紀錄
├── LICENSE
├── pyproject.toml
├── test.sh                 # 根目錄入口，轉呼叫 tash.sh/test.sh
└── README.md
```

## 11. 限制

- 菜單只有一種服務時間分布，沒有區分不同餐點的差異。
- 顧客以最短隊伍選擇窗口，沒有考慮品牌偏好或熟客動線。
- 耐心時間固定用指數分布，尚未支援常數或歷史資料擬合。
- 假設人力在模擬期間固定，不處理輪班、休息與跨時段人力調整。
- 模擬結果為隨機估計；正式決策建議增加 `replications` 並報告信賴區間
  （目前輸出平均值與百分位，未提供信賴區間）。

## 12. AI 使用說明（給 AI 助手與 LLM）

本節可以直接貼給 AI 助手（ChatGPT、Claude、opencode 等），
讓它在回答 `cafeteria-sim` 相關問題時使用正確的參數、單位與指標。
本節同步顯示於 PyPI 專案頁面。

### 12.1 套件定位

- `cafeteria-sim` 是**離散事件模擬**套件，不是 M/M/c 解析公式，
  也不是最佳化求解器的替代品；輸出是帶隨機性的模擬估計。
- 適合回答：「多開一個窗口能減少多少等候？」「在等候目標下，最少需要幾個人？」
- 不支援：多種餐點服務時間、輪班與休息、跨時段人力、信賴區間估計。

### 12.2 安裝與匯入

```bash
pip install cafeteria-sim
cafeteria-sim demo
```

```python
from cafeteria_sim import (
    SimulationConfig,
    compare_windows,
    optimize_staffing,
    run_simulation,
)
```

### 12.3 常用參數與單位

| 參數 | 單位／可選值 | 說明 |
|---|---|---|
| `arrival_rate_per_hour` | 人/小時 | Poisson 到達率 |
| `duration_minutes` | 分鐘 | 模擬長度 |
| `warmup_minutes` | 分鐘 | 暖機期間，不列入統計 |
| `order_windows` | 整數 | 點餐窗口數 |
| `order_mean_s` | 秒 | 平均點餐時間 |
| `order_dist` | `exponential`、`deterministic`、`uniform`、`triangular` | 點餐時間分布 |
| `pickup_mode` | `shared`、`per_window`、`none` | 取餐動線 |
| `pickup_servers` | 整數 | `shared` 模式的取餐檯數 |
| `pickup_mean_s` | 秒 | 平均取餐時間 |
| `max_order_queue` / `max_pickup_queue` | 人 | 隊伍上限，超過即 balk |
| `order_patience_mean_s` / `pickup_patience_mean_s` | 秒 | 耐心上限，超過即 renege |
| `seed` | 整數 | 隨機種子；重現結果必填 |

### 12.4 建議的 AI 工作流程

1. 先跑 `cafeteria-sim demo` 或 `run_simulation` 建立基準情境。
2. 用 `compare_windows(config, [n - 1, n, n + 1], replications=3)` 比較相鄰窗口數。
3. 用 `optimize_staffing(...)` 在等候目標下找最低成本配置。
4. 報告結果時附上完整參數、`seed`、`replications` 與指令，讓結果可重現。

### 12.5 可貼給 AI 的 prompt 範例

```text
請使用 Python 套件 cafeteria-sim 回答我的學餐人力問題。
情境：每小時 120 人到達、3 個點餐窗口、平均點餐 75 秒、
共用 2 個取餐檯、平均取餐 45 秒，模擬 120 分鐘、暖機 10 分鐘。
請：
1. 用 SimulationConfig + run_simulation 算出平均與 P95 總等候時間。
2. 用 compare_windows 比較 2、3、4 個窗口，replications=3、seed=42。
3. 用 optimize_staffing 在平均等候 <= 180 秒、P95 <= 450 秒下找最低成本。
4. 附上完整可執行程式與參數，並說明完成率是否為 100%。
```

### 12.6 AI 回答時應遵守

- 先確認每個參數的單位（到達率是人/小時，服務時間是秒，模擬長度是分鐘）。
- 等候指標是 `total_wait_*`（只含排隊，不含服務時間）；
  `system_time_*` 才是從到達至離開的總時間。
- 常用指標鍵：`arrivals`、`served`、`completion_rate`、`throughput_per_hour`、
  `total_wait_mean_s`、`total_wait_p95_s`、`*_utilization`、`avg_*_queue`、`max_*_queue`。
- 若 `completion_rate < 1`，要說明是 balk（`balked`、`balked_pickup`）
  還是 renege（`reneged_order`、`reneged_pickup`）造成。
- 不要捏造套件未提供的參數或指標；需要新功能時，明確說「目前不支援」。
- 變更窗口數或人力時，提醒使用者使用相同 seed（common random numbers）以降低比較噪聲。
- 單次模擬僅供快速檢查；正式結論建議 `replications >= 3`（或更多）並報告變異。

### 12.7 驗證 AI 產生的程式

```bash
python -m unittest discover -s tests -v
python -m cafeteria_sim run --json --seed 42
```

AI 產生的程式若無法重現，先檢查 seed、單位與 `replications`，
再用 `compare_windows` 或 `optimize_staffing` 交叉驗證。
