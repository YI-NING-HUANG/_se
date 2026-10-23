# HW7：DINO RUN — 離線小恐龍網站應用

> 以 Google Chrome 斷線時出現的離線小恐龍為靈感，實作的無限跑酷小遊戲。
> 網站本身零執行期依賴：不需要 `pip install`，也不需要 `npm install`，`python app.py` 就能跑。
> 只有第一次執行 Playwright E2E 測試前，需要在 `tests/e2e` 安裝測試套件。

---

## 第一部份：網站應用簡介

### 這個網站應用是什麼？

DINO RUN 是一個可以直接在瀏覽器遊玩的無限跑酷網站應用。玩家操作一隻像素風小恐龍，在沙漠中不斷向前跑，閃避仙人掌與翼龍；跑得越遠分數越高，撞到障礙物就遊戲結束。

它不是單純的靜態網頁，而是包含完整前後端與離線能力的小型 Web 應用：

- **前端**：原生 HTML／CSS／JavaScript + Canvas 繪製遊戲，沒有框架、沒有 CDN、沒有外部圖片或音檔。
- **後端**：Python 3 標準庫 `ThreadingHTTPServer` + SQLite，提供靜態檔案與排行榜 API。
- **離線能力**：Service Worker + PWA manifest，第一次載入後可離線遊玩。
- **資料保存**：瀏覽器 `localStorage` 保存個人最高分；SQLite 保存公開排行榜。
- **測試**：Server 單元測試、Web API 系統測試、Playwright 無頭瀏覽器 E2E 測試。

### 一、功能（玩法）

1. **核心玩法**：小恐龍自動向前跑，玩家負責跳躍與蹲下，閃避迎面而來的障礙物；碰撞即遊戲結束，可立即重新開始。
2. **障礙物**：仙人掌有小／大、單株／叢生等變化；分數超過 240 後會出現高、中、低三種高度的翼龍。
3. **分數與難度**：分數為 `floor(跑過的距離 / 10)`；速度從 360 px/s 開始，隨距離線性增加，上限 820 px/s；障礙物間距會依速度調整，避免太難反應。
4. **畫面變化**：每 700 分切換一次白天／夜晚；包含雲朵、星空、地面細節、跳躍與落地粒子效果。
5. **音效**：使用 Web Audio 即時合成跳躍、得分、碰撞等音效，可開關，不需要外部音檔。
6. **最高分**：個人最高分存在 `localStorage`，重新整理或離線遊玩都不會消失。
7. **SQLite 排行榜**：遊戲結束後可輸入 1～16 字的名字送出分數；排行榜顯示 Top 10、總場次、最高分與平均分。
8. **PWA 離線遊玩**：Service Worker 快取 App Shell；排行榜 API 走網路、不進快取，避免離線時顯示舊資料。
9. **手機支援**：響應式版面、點擊畫面跳躍，另有 JUMP／DUCK 觸控按鈕。
10. **輸入與檔案安全**：限制 request body 大小、驗證名字與分數、使用參數化 SQL、阻擋靜態檔案路徑穿越。

### 給第一次從 GitHub 看到的人：如何在電腦上啟動？

這不是純靜態網站；排行榜需要 Python 後端，因此請用下面的方式啟動，而不是只打開 `static/index.html`。這個專案**不需要安裝資料庫，也不需要 `pip install` 或 `npm install` 才能遊玩**，只要電腦有 Python 與現代瀏覽器即可。

#### 需要具備什麼？

| 項目 | 需求 | 說明 |
|---|---|---|
| Python | 3.10 或更新版本 | 執行後端與靜態檔案伺服器；安裝時建議勾選「Add Python to PATH」 |
| 瀏覽器 | Chrome／Edge／Firefox／Safari 等現代瀏覽器 | 執行 Canvas 遊戲與 Service Worker |
| Git | 選用 | 用來 `git clone`；沒有 Git 也可以從 GitHub 下載 ZIP |
| Node.js | 選用，18 以上 | 只有要執行 Playwright E2E 測試才需要，玩遊戲不用 |

#### 啟動步驟

1. **取得專案**：在終端機（Windows PowerShell／命令提示字元，或 macOS／Linux 的 Terminal）執行：

   ```bash
   git clone https://github.com/YI-NING-HUANG/_se.git
   cd _se/homework/HW7
   ```

   如果沒有安裝 Git，也可以在 GitHub 頁面按「Code」→「Download ZIP」，解壓縮後在 `homework/HW7` 資料夾開啟終端機。

2. **確認 Python 已安裝**：

   ```bash
   python --version
   ```

   Windows 若找不到 `python`，可以改用：

   ```bash
   py --version
   ```

3. **啟動網站應用**：

   ```bash
   python app.py
   ```

   Windows 也可以使用：

   ```bash
   py app.py
   ```

4. **開啟瀏覽器**：看到終端機顯示伺服器啟動後，打開：

   <http://127.0.0.1:8787/>

5. **停止伺服器**：回到終端機按 `Ctrl + C`。

補充說明：

- 第一次啟動時會自動建立 `data/scores.db`，不需要手動建表。
- 若 `8787` 連接埠已被占用，可以改用其他埠，例如 `python app.py --port 8788`，並開啟 <http://127.0.0.1:8788/>。
- 若出現 `python` 不是內部或外部命令，代表 Python 沒有加入 PATH；請重新安裝 Python 並勾選「Add Python to PATH」，或改用 `py`。
- 直接雙擊 `static/index.html` 雖然可以玩遊戲，但沒有排行榜，Service Worker 也可能無法運作；建議使用 `python app.py`。

### 二、操作方式

| 操作 | 按鍵／方式 |
|---|---|
| 開始／跳躍 | `Space`、`↑`、`W`、點擊畫面、JUMP 按鈕 |
| 蹲下 | `↓`、`S`、按住 DUCK 按鈕 |
| 暫停／繼續 | `P`、`Esc`、畫面下方「暫停」按鈕 |
| 重新開始 | 遊戲結束後按 `Space`、`R` 或「再玩一次」 |
| 音效開關 | `M` 或右上角音效按鈕 |

遊戲結束後，若分數大於 0，可以輸入名字並按下「存入排行榜」。名字會去除控制字元、合併多餘空白，長度限制 1～16 字。

### 三、主題靈感

這個題目來自 **Google Chrome 在網路斷線時出現的離線小恐龍遊戲**。選擇它作為主題，是因為它具備三個優點：

1. **辨識度高、規則簡單**：玩家一看就知道要跳躍閃避障礙物，不需要複雜教學。
2. **很適合展示離線 Web 技術**：遊戲本身只需要 HTML、CSS、JavaScript 與 Canvas，正好可以搭配 Service Worker 做成 PWA。
3. **核心迴圈小，但延伸空間大**：可以在上方加入排行榜、手機觸控、晝夜變化、音效與自動化測試，把重點放在工程品質而不是美術素材。

這是一個向原版致意的小嘗試，不是複製原版程式碼或畫面；遊戲邏輯、視覺與後端排行榜都是重新實作，並額外加入了 SQLite 排行榜、離線快取、手機操作與三層自動化測試。

### 快速開始

```bash
cd homework/HW7
python app.py
```

開啟 <http://127.0.0.1:8787/> 即可遊玩。

> 預設使用 `8787`，避免與常見的 `8080` 衝突；若要用其他埠，加上 `--port` 即可。
> 資料庫第一次啟動時會自動建立，預設位置是 `data/scores.db`。

常用參數：

```bash
python app.py --host 0.0.0.0 --port 8787
python app.py --db data/scores.db
```

- `--host 0.0.0.0`：讓同一個區網的手機也能連進來。
- `--port`：變更 HTTP 連接埠。
- `--db`：指定 SQLite 資料庫位置。

### 專案結構

```text
HW7/
├─ app.py                  # Python 標準庫 HTTP server + SQLite + API
├─ test.sh                 # 一鍵測試（單元 + 系統 + E2E + JS 語法）
├─ README.md               # 本文件：專案介紹 + 測試說明
├─ .gitignore
├─ data/
│  └─ scores.db            # 執行後自動產生（不進版控）
├─ static/
│  ├─ index.html           # 遊戲頁與排行榜介面
│  ├─ style.css            # 版面、RWD、觸控按鈕
│  ├─ game.js              # Canvas 遊戲主程式
│  ├─ sw.js                # Service Worker（離線快取）
│  ├─ manifest.webmanifest # PWA manifest
│  └─ icon.svg             # 網站圖示
└─ tests/
   ├─ unit/
   │  └─ test_core.py      # 18 個 server 核心單元測試
   ├─ system/
   │  └─ test_api.py       # 19 個 HTTP／Web API 系統測試
   ├─ e2e/
   │  ├─ game.spec.js      # 6 個 Playwright E2E 測試
   │  ├─ playwright.config.js
   │  ├─ package.json
   │  └─ package-lock.json
   ├─ run_tests.sh         # 跑完三層測試與 JS 語法檢查
   └─ test-report.txt      # run_tests.sh 產生的測試報告
```

### 系統架構與 API

```text
Browser
  ├─ GET /                 → static/index.html
  ├─ GET /game.js 等靜態檔  → static/*
  ├─ GET /api/scores       → Python ThreadingHTTPServer → SQLite（讀排行榜）
  ├─ GET /api/stats        → SQLite（讀統計）
  └─ POST /api/scores      → 驗證名字／分數 → SQLite（寫入）

Service Worker
  ├─ 第一次載入：把 index/style/game/manifest/icon 放進 Cache Storage
  ├─ 之後上線：network-first，成功就更新快取
  └─ 離線時：改用快取；導覽請求 fallback 到 index.html
```

前端只用原生 HTML／CSS／JavaScript 與 Canvas；後端只用 Python 3 標準庫：`http.server`、`sqlite3`、`json`、`pathlib`、`urllib`。資料表概念如下：

```text
scores(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT    NOT NULL,
  score      INTEGER NOT NULL,
  created_at TEXT    NOT NULL
)

index idx_scores_rank ON scores(score DESC, id ASC)
```

API 一覽：

| Method | Path | 說明 |
|---|---|---|
| `GET` | `/api/health` | 健康檢查 |
| `GET` | `/api/scores?limit=10` | Top N 排行榜（`limit` 1～50）與統計 |
| `POST` | `/api/scores` | 新增分數，JSON：`{"name":"Dino","score":123}` |
| `GET` | `/api/stats` | 總場次、最高分、平均分 |

範例：

```bash
curl http://127.0.0.1:8787/api/health
curl "http://127.0.0.1:8787/api/scores?limit=5"
curl -X POST http://127.0.0.1:8787/api/scores \
  -H "Content-Type: application/json" \
  -d '{"name":"Dino","score":321}'
```

錯誤情況會回傳 `400`（格式／範圍錯誤）、`404`（不存在的 API 或路徑）、`413`（body 超過 16 KB）。
名字會去除控制字元、合併空白，長度限制 1～16 字；分數必須是 0～1,000,000 的整數。

### 遊戲規則與難度

- 分數：`floor(跑過的距離 / 10)`，跑得越遠分數越高。
- 速度：從 360 px/s 開始，隨距離線性增加，上限 820 px/s。
- 障礙物間距會依目前速度調整，避免速度太快時無法反應。
- 分數超過 240 後開始出現翼龍；每 700 分切換一次白天／夜晚。

### 離線遊玩與 PWA

1. 用 `python app.py` 啟動，透過 `http://127.0.0.1:8787/` 或區網 IP 開啟（Service Worker 需要 localhost 或 HTTPS）。
2. 第一次載入會註冊 `sw.js` 並快取 App Shell。
3. 之後把伺服器關掉，或開發者工具選 Offline，重新整理仍可看到遊戲並遊玩。
4. 離線時排行榜無法載入／送出，但最高分仍存在瀏覽器 `localStorage`，遊戲不受影響。

> 直接雙擊 `static/index.html`（`file://`）也可以玩，但瀏覽器不會啟用 Service Worker，
> 且沒有後端排行榜。建議用 `python app.py` 開啟。

---

## 第二部份：測試設計與實作

### 測試策略

題目要求 **Server 一定要有單元測試**（例如 Rust 後端），**Client 可以不測**（例如 Node.js 前端）。本專案的 Server 是 Python，Client 是原生 JavaScript／Canvas，因此測試安排如下：

- Server 端同時撰寫 **單元測試** 與 **系統測試**。
- Client 的 Canvas 遊戲邏輯沒有另外建立 JavaScript 單元測試，改用 **Playwright E2E** 實際操作瀏覽器驗證。
- 三層測試都放在 `tests/` 下，並提供 `test.sh` 一鍵執行。

| 層級 | 工具 | 檔案 | 數量 | 主要對象 | 是否啟動服務 |
|---|---|---|---|---|---|
| 單元測試 | Python `unittest` | `tests/unit/test_core.py` | 18 | Server 核心函式與 SQLite 類別 | 否 |
| 系統測試 | Python `unittest` + `urllib`／`http.client` + `subprocess` | `tests/system/test_api.py` | 19 | 真實 HTTP Server 與 Web API | 是，暫存埠與暫存 DB |
| E2E 測試 | Playwright + 無頭 Chrome | `tests/e2e/game.spec.js` | 6 | 真實瀏覽器、Canvas、Service Worker、手機操作 | 是，Playwright `webServer` |

### 1. 單元測試（Server 必測）

**位置**：`tests/unit/test_core.py`｜**數量**：18 個測試｜**工具**：`unittest`、`tempfile`、`sqlite3`、`contextlib.closing`

這一層直接 `from app import Leaderboard, clean_name, valid_score`，把 Server 的核心邏輯當成一般 Python 函式／類別測試。**不啟動 HTTP Server、不開 socket、不使用瀏覽器**，所以速度快、失敗時容易定位。

測試對象與涵蓋範圍：

| 測試對象 | 測試重點 |
|---|---|
| `clean_name()` | 去除頭尾空白、合併連續空白、控制字元轉空白、1～16 字邊界、17 字拒絕、全空白拒絕、非字串拒絕、中文與 emoji 保留 |
| `valid_score()` | 0 與 1,000,000 邊界、負數、超上限、布林值、浮點數、字串、`None` 等錯誤型別 |
| `Leaderboard` | 新資料庫為空、新增後回傳 record 與 rank、同分依插入順序、Top N 排序、limit、平均分統計、跨 instance 持久化、Unicode 名字、排名索引存在 |

代表性的測試方法：

- `CleanNameUnitTests`：`test_trims_and_collapses_spaces`、`test_control_characters_become_spaces`、`test_length_boundaries`、`test_only_whitespace_is_rejected`、`test_non_string_is_rejected`、`test_unicode_name_is_kept`。
- `ValidScoreUnitTests`：`test_valid_boundaries`、`test_out_of_range_is_rejected`、`test_wrong_types_are_rejected`。
- `LeaderboardUnitTests`：`test_new_database_is_empty`、`test_add_returns_record_and_rank`、`test_rank_uses_score_and_insert_order`、`test_top_orders_by_score_then_id`、`test_top_respects_limit`、`test_stats_aggregates_scores`、`test_persistence_across_instances`、`test_unicode_name_round_trip`、`test_rank_index_exists`。

**隔離方式**：每個 `LeaderboardUnitTests` 測試都在 `tempfile.TemporaryDirectory()` 中建立獨立的 `unit.db`，測試結束自動刪除，不會污染 `data/scores.db`。

執行方式：

```bash
python -m unittest discover -s tests/unit -t . -v
```

### 2. 系統測試（Web API 測試）

**位置**：`tests/system/test_api.py`｜**數量**：19 個測試｜**工具**：`unittest`、`subprocess`、`urllib.request`、`http.client`、`sqlite3`、`tempfile`

這一層會用 `subprocess` 真的啟動 `python app.py`，使用 **隨機空閒埠** 與 **暫存 SQLite 資料庫**，再透過 HTTP 請求驗證實際行為。這是對 Web API 契約與前後端整合的測試，不是只呼叫 Python 函式。

測試生命週期：

- `setUpClass()`：建立暫存目錄、找空閒埠、啟動 Server，輪詢 `/api/health` 直到就緒。
- `setUp()`：每個測試前清空 `scores` 資料表，讓測試互不影響。
- `tearDownClass()`：終止 Server、等待結束、刪除暫存目錄。

涵蓋範圍：

| 類別 | 測試內容 |
|---|---|
| 基本與靜態資源 | `/api/health`、首頁、CSS／JS／Service Worker／manifest／icon、favicon、Service Worker 快取清單 |
| 排行榜 API | 空排行榜、新增分數、排名、同分插入順序、Top N、`limit` 邊界、統計值 |
| 輸入驗證 | 非法名字、非法分數、布林值、錯誤 JSON、空 body、過大 body（413）、名字清洗 |
| 安全與協定 | 路徑穿越（`../`、`%2f`、`%5c`）、未知 API／靜態路徑、未知 POST、HEAD、Cache-Control、`X-Content-Type-Options` |
| 前端契約 | 檢查 `game.js` 是否包含 `requestAnimationFrame`、`spawnBird`、`spawnCactus`、`localStorage`、`serviceWorker`、`/api/scores`、`dinoBox`、`KeyP` 等關鍵功能 |

代表性測試：

- `test_health`、`test_index_page`、`test_static_assets`
- `test_scores_start_empty`、`test_post_score_and_ranking`、`test_tied_scores_keep_insert_order`
- `test_invalid_scores_are_rejected`、`test_invalid_json_and_body`、`test_name_is_sanitized`
- `test_limit_is_clamped`、`test_stats_endpoint`
- `test_path_traversal_is_blocked`、`test_unknown_paths`、`test_unknown_post_route`
- `test_head_request`、`test_cache_headers_and_nosniff`、`test_favicon_is_served`
- `test_service_worker_has_cache_shell`、`test_frontend_contains_required_features`

執行方式：

```bash
python -m unittest discover -s tests/system -t . -v
```

### 3. E2E 測試（無頭瀏覽器，Playwright）

**位置**：`tests/e2e/game.spec.js`｜**數量**：6 個測試｜**工具**：Playwright + 系統已安裝的 Chrome（`channel: "chrome"`），以無頭模式執行

E2E 測試會實際開啟瀏覽器、載入頁面、按鍵盤、點擊按鈕、讀取 Canvas 遊戲狀態，並驗證 Service Worker 離線行為。這是三層測試中最接近真實使用者的一層。

Playwright 設定（`playwright.config.js`）：

- `baseURL`：`http://127.0.0.1:8799`
- `webServer`：自動啟動 `python ../../app.py --host 127.0.0.1 --port 8799 --db .tmp/e2e.db`
- 使用 `.tmp/e2e.db` 暫存資料庫，不影響正式資料。
- `workers: 1`、`fullyParallel: false`，避免測試互相競爭資料庫。
- `headless: true`、`channel: "chrome"`，使用系統 Chrome，不需要下載 Chromium。
- 失敗時保留 trace 與截圖；報告輸出到 `playwright-report/` 與 `test-results/results.json`。

6 個測試案例：

| 測試 | 驗證內容 |
|---|---|
| 首頁載入、排行榜連線、無 JS 錯誤 | 標題、遊戲 Canvas、排行榜連線狀態、沒有 page error／console error |
| 鍵盤控制：開始、跳躍、蹲下、暫停與繼續 | 按 `Space` 開始、`ArrowUp` 跳躍後離地再落地、`ArrowDown` 蹲下、`P` 暫停與繼續 |
| 遊戲結束後可送出分數並更新排行榜 | 不操作直到 GAME OVER，輸入名字送出，確認 UI 顯示與 `/api/scores` 實際寫入 |
| 排行榜會顯示 SQLite 中的既有資料 | 先用 API 寫入 999999 分，重新載入頁面確認排行榜第一名顯示該筆資料 |
| Service Worker 離線後仍可載入並開始遊戲 | 確認快取包含 `/`、`index.html`、`style.css`、`game.js`、manifest、icon；切換 Offline 後重新整理仍可開始遊戲 |
| 手機版：觸控按鈕可開始遊戲並跳躍 | 390×844、`hasTouch`、`isMobile`，確認 JUMP／DUCK 可見，點擊開始與跳躍成功 |

為了讓測試能觀察遊戲內部狀態，`game.js` 提供唯讀的除錯介面：

```javascript
window.__dinoRun.snapshot()
```

回傳目前 `state`、分數、恐龍的 `x`／`y`／`onGround`／`ducking` 等資訊，E2E 用它判斷跳躍、蹲下、暫停與遊戲結束，不需要讀取 Canvas 像素。

第一次執行前安裝套件：

```bash
cd tests/e2e
npm install
```

執行：

```bash
npx playwright test
# 或
npm test
```

`npm test` 會先執行 `pretest` 清理 `.tmp/`、`test-results/`、`playwright-report/`，再跑測試。

如果電腦沒有安裝 Chrome，可以改用 Playwright 的 Chromium：

```bash
npx playwright install chromium
```

然後把 `playwright.config.js` 中的 `channel: "chrome"` 移除。

### 測試執行方式

從 `homework/HW7` 執行一鍵測試：

```bash
bash test.sh
```

`test.sh` 會依序執行：

1. Server 單元測試（18）
2. Server 系統測試（19）
3. `node --check` 檢查 `static/game.js` 與 `static/sw.js` 語法
4. Playwright E2E 測試（6）

等價指令：

```bash
bash tests/run_tests.sh
```

個別執行：

```bash
# 單元測試
python -m unittest discover -s tests/unit -t . -v

# 系統測試
python -m unittest discover -s tests/system -t . -v

# E2E
cd tests/e2e
npm install
npx playwright test
```

測試報告位置：

| 內容 | 位置 |
|---|---|
| 三層合併文字報告 | `tests/test-report.txt` |
| Playwright HTML 報告 | `tests/e2e/playwright-report/index.html` |
| Playwright JSON 結果 | `tests/e2e/test-results/results.json` |
| 失敗截圖／trace | `tests/e2e/test-results/artifacts/` |

### 目前測試結果

- 單元測試：**18 passed**
- 系統測試：**19 passed**
- E2E 測試：**6 passed**
- JavaScript 語法檢查：**OK**
- 總結：**ALL CHECKS PASSED**

合計 **43 個測試通過**。完整輸出可查看 `tests/test-report.txt`。

### 測試與需求對照

| 需求 | 本專案實作 | 位置 |
|---|---|---|
| Server 一定要有單元測試 | Python Server 核心函式與 SQLite 類別，共 18 個測試 | `tests/unit/test_core.py` |
| Client 可以不測 | Canvas 遊戲邏輯不另寫 JS unit test，改由 E2E 操作瀏覽器驗證 | `tests/e2e/game.spec.js` |
| 系統測試／Web API 測試 | 真實啟動 HTTP Server，測試 API、靜態資源、錯誤碼、標頭與安全 | `tests/system/test_api.py` |
| E2E 測試（無頭瀏覽器，Playwright） | Playwright + 無頭 Chrome，測試遊戲操作、排行榜、離線與手機版 | `tests/e2e/game.spec.js` |
| 離線／PWA | 系統測試檢查 Service Worker 快取清單；E2E 實際切換 Offline 重新載入 | `tests/system/test_api.py`、`tests/e2e/game.spec.js` |
| 手機操作 | E2E 使用 390×844、`hasTouch`、`isMobile` 驗證觸控按鈕 | `tests/e2e/game.spec.js` |
| 安全性 | 單元測試驗證輸入清洗；系統測試驗證路徑穿越、body 大小與錯誤處理 | `tests/unit/test_core.py`、`tests/system/test_api.py` |

### 測試設計取捨

- **為什麼 Client 不寫單元測試？** Canvas 遊戲邏輯與 DOM、`requestAnimationFrame`、瀏覽器事件高度耦合，硬拆成單元測試容易測到實作細節。用 Playwright 直接操作瀏覽器，更接近真實使用情境，也能同時驗證 Canvas、鍵盤、觸控與 Service Worker。
- **為什麼系統測試要真的開 Server？** 只呼叫 Python 函式無法驗證路由、HTTP 狀態碼、標頭、JSON 格式與 SQLite 整合；真的啟動 Server 才能抓到這些問題。
- **測試隔離**：單元測試使用暫存 DB；系統測試使用暫存目錄、隨機埠，且每個測試前清空資料表；E2E 使用 `.tmp/e2e.db`，不影響 `data/scores.db`。
- **降低不穩定**：E2E 使用 `expect.poll()` 等待遊戲狀態，而不是固定 sleep；Playwright 設定單一 worker，避免多個測試同時寫入同一個資料庫。
- **目前未涵蓋**：沒有像素級視覺回歸、沒有效能／壓力測試、沒有跨瀏覽器矩陣（目前使用系統 Chrome）。這些可以作為後續擴充。

### 疑難排解

- **E2E 找不到 Chrome**：本設定使用系統 Chrome。請安裝 Google Chrome，或執行 `cd tests/e2e && npx playwright install chromium`，再把 `playwright.config.js` 的 `channel: "chrome"` 移除。
- **npm 出現 `EALLOWSCRIPTS`**：此環境的 npm 有 allow-scripts 限制，可改用：
  ```bash
  cd tests/e2e
  env -u npm_config_allow_scripts npm install
  ```
- **連接埠 8799 被佔用**：修改 `tests/e2e/playwright.config.js` 的 `PORT` 常數。
- **E2E 尚未安裝套件**：先執行 `cd tests/e2e && npm install`，或直接執行 `bash test.sh`，`run_tests.sh` 會偵測並嘗試安裝。

### 設計重點

- **零執行期依賴**：網站本身只需要 Python 3.10+ 即可執行；Playwright 套件只用於測試。
- **SQLite 寫入安全**：使用參數化查詢；每次請求建立連線並關閉，啟用 WAL 與 `busy_timeout`。
- **輸入防護**：限制 body 大小、名字長度、分數範圍，拒絕非整數與布林值。
- **靜態檔案安全**：解析後檢查是否仍在 `static/` 內，阻擋路徑穿越。
- **離線優先**：Service Worker 不快取 `/api/`，避免排行榜資料被舊快取污染。
- **可測試性**：`window.__dinoRun.snapshot()` 提供唯讀遊戲狀態，方便 E2E 驗證。

### 已知限制

- 排行榜需要後端；若只把 `static/` 放到 GitHub Pages，只有遊戲與離線功能，沒有排行榜。
- 沒有帳號系統，名字可重複，排行榜是公開的。
- 音效受瀏覽器自動播放政策限制，需要先有使用者互動（開始遊戲或用滑鼠點擊）才會發聲。
- E2E 目前只使用系統 Chrome，尚未涵蓋 Firefox、Safari 或不同作業系統的瀏覽器矩陣。
