# HW9：DINO RUN on Cloudflare — Workers + D1 全球排行榜

> 把 HW7 的離線小恐龍搬上 Cloudflare：前端由 Static Assets 託管，
> 排行榜 API 跑在 Cloudflare Workers，分數存進 D1（SQLite）。
>
> 線上示範（Wrangler temporary preview 帳號）：
> <https://hw9-dino-run.deciduous-device.workers.dev>
>
> 本機開發：`npm run dev` → <http://localhost:8787>

---

## 1. 專案緣起：延續哪個網站應用

本專案延續先前作業的 **DINO RUN 小恐龍網站應用**；這個應用在目前 repo 中位於 `homework/HW7`。

HW7 已經有完整遊戲、PWA 離線能力與 SQLite 排行榜，但它的 README 也留下一個明確限制：

> 「排行榜需要後端；若只把 `static/` 放到 GitHub Pages，只有遊戲與離線功能，沒有排行榜。」

HW9 的任務，就是把這個網站應用真正搬到雲端：

- **保留 HW7 的成果**：Canvas 遊戲、`style.css`、`index.html`、Service Worker、PWA manifest 全部沿用。
- **補上 HW7 的缺口**：把 Python 後端改成 Cloudflare Workers，把本機 SQLite 改成 Cloudflare D1。
- **讓排行榜上網**：任何人打開同一個網址，都會看到同一份全球排行榜，不需要自己開伺服器。
- **保持 API 相容**：HW9 的 `/api/health`、`/api/scores`、`/api/stats` 與 HW7 格式一致，前端幾乎不用改。
- **增加分享方式**：除了 Cloudflare 完整版，還能產生單檔 HTML，放到 GitHub Pages 或直接傳給別人。

> 編號說明：目前 repo 沒有 `HW5` 資料夾，實際被延伸的網站應用是 `HW7` 的 DINO RUN。
> 若課程把同一個小恐龍應用編為 HW5，請以 `homework/HW7` 的內容為準。

一句話總結：**HW7 做出了好玩的遊戲，HW9 讓它的排行榜真正上網。**

---

## 2. 用 Cloudflare 製作了哪裡、提供哪些功能

### 2.1 從 HW7 搬到 Cloudflare 的部分

| 原本在 HW7 | HW9 改成 | 使用的 Cloudflare 服務 |
|---|---|---|
| Python `ThreadingHTTPServer` | 邊緣執行的 Worker 程式 | Cloudflare Workers |
| `static/` 由 Python 讀檔回傳 | 由 Cloudflare 全球節點直接提供 | Workers Static Assets |
| `data/scores.db`（本機 SQLite） | 雲端 SQLite 相容資料庫 | Cloudflare D1 |
| `python app.py` 啟動 | `wrangler dev` 本機模擬 | Wrangler |
| 手動開 Port、顧機器 | `wrangler deploy` 一鍵部署 | Wrangler |
| 終端機 log | 後台可查請求與錯誤日誌 | Workers Observability |

具體來說，Cloudflare 上做了這些事：

- **前端託管**：把 `public/` 的 `index.html`、`style.css`、`game.js`、`sw.js`、`manifest.webmanifest`、`icon.svg` 全部交給 Static Assets。
- **排行榜 API**：用 `src/index.js` 實作 `/api/health`、`/api/scores`、`/api/stats`，部署成 Worker。
- **全球資料庫**：用 `migrations/0001_init.sql` 在 D1 建立 `scores` 資料表與排名索引。
- **部署設定**：用 `wrangler.jsonc` 綁定 `DB`（D1）與 `ASSETS`（靜態資產），設定 compatibility date 與 observability。
- **跨網域分享**：Worker 加上 CORS 與 `OPTIONS` preflight，讓 GitHub Pages 上的單檔 HTML 也能呼叫排行榜 API。
- **單檔發布**：用 `scripts/build-standalone.mjs` 把整個前端內嵌成一個 `index.html`，仍然連回同一個 Worker。

### 2.2 遊戲功能

- 無限跑酷：小恐龍自動前進，玩家按空白鍵／↑／W 跳躍，按 ↓／S 蹲下。
- 障礙物：仙人掌有小／大、單株／叢生；分數超過 240 後會出現不同高度的翼龍。
- 分數與難度：分數依距離計算，速度從 360 px/s 線性增加到 820 px/s。
- 畫面效果：白天／夜晚切換、雲朵、星空、地面細節、跳躍與落地粒子。
- 音效：用 Web Audio 即時合成，不需要外部音檔，可開關。
- 操作支援：鍵盤、滑鼠點擊、手機觸控 JUMP／DUCK 按鈕。
- 暫停與重來：`P`／`Esc` 暫停，遊戲結束後可立即重新開始。

### 2.3 全球排行榜功能

- 遊戲結束後可輸入 1～16 字的名字，把分數送到 Cloudflare D1。
- 排行榜顯示 Top 10、總場次、最高分、平均分。
- 送出後立刻回傳目前排名；同分時先送出的人排名較前。
- 排行榜 API 使用 `ORDER BY score DESC, id ASC`，並用參數化查詢計算排名。
- 名字會去除控制字元、合併多餘空白；分數限制為 0～1,000,000 的整數。
- 排行榜資料不快取（`Cache-Control: no-store`），避免看到過期結果。

### 2.4 API 與安全功能

- **輸入驗證**：名字長度、分數範圍、`limit` 範圍、JSON 型別都檢查。
- **Body 上限**：請求超過 16 KiB 回傳 413，避免大量內容打爆 Worker。
- **SQL injection 防護**：所有 D1 查詢都使用 `bind()` 參數化。
- **XSS 防護**：前端用 `textContent` 顯示名字，不把使用者輸入當 HTML。
- **一致的錯誤格式**：400、404、405、413、500 都回傳 JSON 與 `ok: false`。
- **CORS**：允許靜態單檔版跨網域讀寫排行榜，並正確處理 preflight。
- **可觀測性**：D1 失敗時寫 `console.error`，可在 Cloudflare 後台查看。

### 2.5 分享與離線功能

- **Cloudflare 完整版**：`https://hw9-dino-run.<subdomain>.workers.dev`，含 Static Assets、Worker、D1。
- **單檔 HTML 版**：`npm run build:standalone` 產生 `index.html`，可直接開、可放 GitHub Pages。
- **GitHub Pages 連結**：推上 GitHub 後可用 `https://yi-ning-huang.github.io/_se/homework/HW9/`。
- **PWA 離線**：Service Worker 快取 App Shell，離線仍可玩遊戲。
- **離線排行榜策略**：`/api/` 不進快取，離線時排行榜顯示「離線中」，恢復連線後重新整理即可同步。
- **本機最高分**：個人最高分存在 `localStorage`，即使排行榜暫時離線也不會消失。

---

## 3. 系統架構

```text
                        Browser
                           │
          ┌────────────────┴─────────────────┐
          │                                  │
          ▼                                  ▼
  靜態資源請求                          /api/* 請求
  / /style.css /game.js                 /api/health
  /manifest.webmanifest                 /api/scores
  /sw.js /icon.svg                      /api/stats
          │                                  │
          ▼                                  ▼
  Cloudflare Static Assets          Cloudflare Worker
  （public/ 目錄）                   （src/index.js）
                                             │
                                             ▼
                                    Cloudflare D1
                                    scores 資料表
                                  （SQLite 相容關聯式資料庫）

  Browser 內另有一個 Service Worker：
  只快取上方靜態 App Shell；/api/* 直接走網路。

  單檔 HTML 版（index.html）：
  可直接放在 GitHub Pages，透過 CORS 呼叫同一個 Worker API。
```

### 一次「送出分數」的流程

1. 瀏覽器 `POST /api/scores`，body 為 `{"name":"Neo","score":320}`。
2. Static Assets 找不到 `/api/scores` 這個檔案，請求交給 Worker。
3. Worker 驗證 JSON、名字與分數，使用 parameterized statement 寫入 D1。
4. Worker 查詢同分且 id 較小的筆數，算出排名。
5. 回傳 `201 Created`、新紀錄與排名。
6. 前端重新 `GET /api/scores?limit=10`，更新排行榜。

> 名詞區分：**Cloudflare Worker** 是跑在 Cloudflare 邊緣網路上的伺服器端程式；
> **Service Worker** 是瀏覽器裡的離線快取代理。兩者名字很像，但完全不同。

---

## 4. 用到的 Cloudflare 服務

| 服務 | 在本專案的角色 | 設定位置 |
|---|---|---|
| Cloudflare Workers | 執行 `/api/*`、驗證輸入、存取 D1、回傳 JSON | `src/index.js`、`wrangler.jsonc` |
| Workers Static Assets | 託管 `public/` 的 HTML、CSS、JS、SVG、manifest | `wrangler.jsonc` 的 `assets` |
| Cloudflare D1 | 儲存全球排行榜資料（SQLite 語法） | `wrangler.jsonc` 的 `d1_databases`、`migrations/` |
| Wrangler | 本機開發伺服器、D1 migration、打包與部署 | `package.json`、`wrangler.jsonc` |
| Workers Observability | 在 Cloudflare 後台查看 Worker 日誌與錯誤 | `observability.enabled` |

前端另外使用瀏覽器原生 Service Worker 與 PWA manifest，這不是 Cloudflare 服務，但兩者常被混淆，特別在此說明。

---

## 5. 專案結構

```text
HW9/
├── README.md                     # 本文件
├── index.html                    # 單檔分享版（由 build:standalone 產生）
├── package.json                  # npm scripts 與 Wrangler 開發依賴
├── package-lock.json
├── wrangler.jsonc                # Worker、Static Assets、D1 綁定
├── .gitignore                    # 忽略 node_modules、.wrangler、claim URL
├── scripts/
│   └── build-standalone.mjs      # 把 public/ 內嵌成單一 index.html
├── migrations/
│   └── 0001_init.sql             # scores 資料表與排名索引
├── src/
│   └── index.js                  # Cloudflare Worker API
├── public/                       # 由 Static Assets 託管
│   ├── index.html                # 遊戲頁
│   ├── style.css
│   ├── game.js                   # Canvas 遊戲與排行榜前端
│   ├── sw.js                     # Service Worker（不快取 /api/）
│   ├── manifest.webmanifest      # PWA manifest
│   └── icon.svg
└── tests/
    ├── unit/
    │   └── validation.test.js    # 純函式單元測試（Node test runner）
    ├── api/
    │   └── api.test.js           # 真實 HTTP + D1 整合測試
    └── test-report.txt           # 最近一次 test.sh 的完整報告
```

---

## 6. 本機開發

### 需求

| 項目 | 版本 | 說明 |
|---|---|---|
| Node.js | 20 以上 | 執行 Wrangler 與 Node test runner |
| npm | 10 以上 | 安裝開發依賴 |
| 瀏覽器 | 現代 Chrome／Edge／Firefox／Safari | 玩遊戲與測 Service Worker |
| Cloudflare 帳號 | 部署時才需要 | 本機開發不需要登入 |

### 啟動步驟

```bash
cd homework/HW9
npm install

# 第一次先建立本機 D1 資料表
npm run db:migrate:local

# 套用 migration 後啟動 Wrangler 本機伺服器
npm run dev
```

開啟 <http://localhost:8787/>。

`npm run dev` 實際等於：

```bash
npm run db:migrate:local
wrangler dev --port 8787
```

本機 D1 資料庫放在 `.wrangler/state/`，不會碰到雲端資料。停止伺服器按 `Ctrl + C`。

### 常用指令

| 指令 | 作用 |
|---|---|
| `npm run dev` | 套用本機 migration 並啟動 `wrangler dev` |
| `npm run db:migrate:local` | 對本機 D1 套用 `migrations/` |
| `npm run db:migrate:remote` | 對雲端 D1 套用 migration（部署前） |
| `npm run deploy` | `wrangler deploy` 部署到 Cloudflare |
| `npm test` | 執行 `bash test.sh` 全套測試 |

### 疑難排解

- **`npm install` 出現 `EALLOWSCRIPTS`**：此環境的 npm 啟用了 allow-scripts 限制，可改用：

  ```bash
  env -u npm_config_allow_scripts npm install
  ```

- **連接埠 8787 被占用**：改用 `wrangler dev --port 8788`。
- **Wrangler 說找不到 D1**：先跑 `npm run db:migrate:local`。
- **Service Worker 快取舊版**：重新整理兩次，或在 DevTools → Application → Service Workers 按 Unregister；`sw.js` 的 `VERSION` 已提升到 `dino-run-v2.0.0`。

---

## 7. 部署到自己的 Cloudflare 帳號

> 目前 `wrangler.jsonc` 裡的 `database_id` 是本次示範用 temporary preview 帳號建立的 D1。
> **要部署到自己的帳號時，一定要換成你自己建立的 database_id。**

### 步驟

1. **登入 Cloudflare**

   ```bash
   npx wrangler login
   ```

   瀏覽器會開啟授權頁；完成後回到終端機。

2. **建立 D1 資料庫**

   ```bash
   npx wrangler d1 create hw9-dino-run
   ```

   輸出會包含：

   ```json
   {
     "binding": "DB",
     "database_name": "hw9-dino-run",
     "database_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   }
   ```

3. **把 `database_id` 填進 `wrangler.jsonc`**

   ```jsonc
   "d1_databases": [
     {
       "binding": "DB",
       "database_name": "hw9-dino-run",
       "database_id": "你的-database-id",
       "migrations_dir": "migrations"
     }
   ]
   ```

   `binding` 必須保持 `DB`，因為 Worker 內使用 `env.DB`。

4. **對雲端 D1 套用 migration**

   ```bash
   npm run db:migrate:remote
   ```

   確認輸出顯示 `0001_init.sql ✅`。

5. **部署 Worker**

   ```bash
   npm run deploy
   ```

   成功後會印出 `https://hw9-dino-run.<你的-subdomain>.workers.dev`。
   若網址和原本不同，記得重新產生單檔版：

   ```bash
   DINO_API_BASE="https://你的-worker.workers.dev" npm run build:standalone
   ```

6. **驗證**

   ```bash
   curl https://hw9-dino-run.<你的-subdomain>.workers.dev/api/health
   curl https://hw9-dino-run.<你的-subdomain>.workers.dev/api/scores
   ```

### 沒有帳號也想先看效果？

Wrangler 支援 temporary preview 帳號：

```bash
npx wrangler d1 create hw9-dino-run --temporary
# 把輸出的 database_id 填進 wrangler.jsonc
npx wrangler d1 migrations apply DB --remote --temporary
npx wrangler deploy --temporary
```

Wrangler 會印出一個 claim URL 與約 60 分鐘的認領期限。temporary 帳號適合展示，不適合長期營運；若要保留資源，請在期限內認領，或直接用自己的 Cloudflare 帳號照上面的正式步驟部署。

本次 HW9 的線上示範即是用這個方式建立。本次的 claim URL 會放在 `.claim-url.txt`（已列入 `.gitignore`），請在 60 分鐘內開啟並完成認領；逾期 temporary 帳號與資源會被刪除。

---

## 8. 單檔 HTML 分享版（GitHub Pages 可直接開）

除了 Cloudflare 上的完整網站，本專案也提供一份**只有一個 HTML 檔案**的版本：

```bash
npm run build:standalone
```

產生 `HW9/index.html`（約 44 KB），裡面包含：

- 遊戲 HTML 與全部 CSS。
- 全部遊戲 JavaScript。
- data URI 圖示。
- `window.DINO_API_BASE = "https://hw9-dino-run.deciduous-device.workers.dev"`。

它仍然會呼叫同一個 Cloudflare Worker + D1 取得全球排行榜。Worker 已加上 CORS，所以從 GitHub Pages、其他靜態空間或本機開啟都能連線。

### 放到 GitHub Pages

把 `HW9/` 推上 GitHub 後，若 Pages 從 repo 根目錄發布，網址會是：

<https://yi-ning-huang.github.io/_se/homework/HW9/>

這個網址會直接載入單檔版 `index.html`。其他人點連結就能玩，排行榜與 Cloudflare 版共用同一份 D1 資料。

> 單檔版可直接雙擊開啟；若瀏覽器對 `file://` 的跨網域請求較嚴格，建議改用 GitHub Pages 或任何靜態伺服器。

已用本機靜態伺服器 + 無頭 Chrome 實測單檔版：排行榜顯示「即時同步 Cloudflare D1 全球排行榜」、沒有 console error，按下開始後遊戲狀態為 `running`。

### 換成自己的 Worker 網址

若重新部署後 Worker 網址不同，重新產生單檔版即可：

```bash
DINO_API_BASE="https://你的-worker.workers.dev" npm run build:standalone
```

Windows PowerShell：

```powershell
$env:DINO_API_BASE="https://你的-worker.workers.dev"; npm run build:standalone
```

### 單檔版與完整版的差異

| 項目 | Cloudflare 完整版 | 單檔 HTML 版 |
|---|---|---|
| 主要網址 | `https://hw9-dino-run.<subdomain>.workers.dev` | GitHub Pages 或任何靜態空間 |
| 靜態檔案 | Cloudflare Static Assets | 全部內嵌在一個 HTML |
| 排行榜 | Worker + D1 | 相同，透過 CORS 呼叫 Worker |
| PWA／Service Worker | 有 | 無（沒有獨立 `sw.js`） |
| 離線遊戲 | 有 | 載入後可玩；重新整理需要網路 |

---

## 9. API 規格

前端與 HW7 使用相同的 API 契約，因此 HW7 的 `game.js` 幾乎不用改。

### `GET /api/health`

```json
{
  "ok": true,
  "service": "dino-run",
  "version": "2.0",
  "runtime": "cloudflare-workers",
  "database": "d1"
}
```

### `GET /api/scores?limit=10`

- `limit` 可省略，預設 10，範圍夾在 1～50。
- 非整數會回傳 400。

```json
{
  "ok": true,
  "scores": [
    {
      "id": 1,
      "name": "Neo",
      "score": 320,
      "created_at": "2026-11-07T15:38:50.057Z"
    }
  ],
  "stats": {
    "games": 1,
    "best": 320,
    "average": 320
  }
}
```

### `GET /api/stats`

```json
{
  "ok": true,
  "stats": { "games": 1, "best": 320, "average": 320 }
}
```

### `POST /api/scores`

請求：

```json
{ "name": "Neo", "score": 320 }
```

成功：`201 Created`

```json
{
  "ok": true,
  "record": {
    "id": 1,
    "name": "Neo",
    "score": 320,
    "created_at": "2026-11-07T15:38:50.057Z"
  },
  "rank": 1
}
```

錯誤狀態：

| 狀態 | 情境 |
|---|---|
| 400 | JSON 格式錯誤、JSON 非物件、名字或分數不合法、`limit` 非整數 |
| 404 | 未知的 `/api/*` 路徑 |
| 405 | 不支援的 HTTP 方法（附 `Allow` header） |
| 413 | 請求內容超過 16 KiB |
| 500 | D1 查詢／寫入失敗 |

所有 API 回應都帶有：

```text
Cache-Control: no-store
X-Content-Type-Options: nosniff
```

### curl 範例

```bash
curl -X POST https://你的網址/api/scores \
  -H "Content-Type: application/json" \
  -d '{"name":"Neo","score":320}'

curl "https://你的網址/api/scores?limit=10"
```

---

## 10. D1 資料表與排名邏輯

`migrations/0001_init.sql`：

```sql
CREATE TABLE IF NOT EXISTS scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  score INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scores_rank ON scores (score DESC, id ASC);
```

- `AUTOINCREMENT`：確保同分時可以比較先後。
- 排行榜排序：`ORDER BY score DESC, id ASC`。
- 送出後的排名：

  ```sql
  SELECT COUNT(*) + 1 AS rank FROM scores
  WHERE score > ? OR (score = ? AND id < ?);
  ```

  也就是「分數比我高的人數 + 同分但比我早送出的人數 + 1」。
- 所有查詢都使用 `bind()` 參數化，不拼接使用者輸入。

新增 migration 時，在 `migrations/` 放入 `0002_xxx.sql`，再執行：

```bash
npm run db:migrate:local    # 本機
npm run db:migrate:remote   # 雲端
```

---

## 11. 測試

一鍵執行：

```bash
bash test.sh
```

或：

```bash
npm test
```

### test.sh 做了什麼

1. 檢查 `src/index.js`、`public/game.js`、`public/sw.js` 的 JavaScript 語法。
2. 對本機 D1 套用 migration。
3. 清空本機測試資料庫，確保測試可重現。
4. 執行 `wrangler deploy --dry-run`，驗證打包與 `wrangler.jsonc` 設定（不會真的部署）。
5. 執行 `npm run build:standalone`，確認單檔 HTML 能產生且沒有殘留外部 JS 參照。
6. 啟動 `wrangler dev`，等待 `/api/health` 就緒。
7. 執行單元測試與真實 HTTP + D1 整合測試。
8. 彙總結果並寫入 `tests/test-report.txt`。

### 目前結果

```text
測試案例：22（PASS=22 FAIL=0）
測試步驟：PASS=7 FAIL=0
ALL CHECKS PASSED
```

- 單元測試：7 個（`tests/unit/validation.test.js`）
- API／整合測試：15 個（`tests/api/api.test.js`）
- 合計：22 個測試

### 測試涵蓋範圍

| 類型 | 內容 |
|---|---|
| 純函式 | 名字清洗、Unicode 長度、分數範圍、`limit` 預設與夾限 |
| 健康檢查 | `/api/health` 回報 Workers + D1 |
| 排行榜 | 空榜統計、寫入、排序、同分先後、Top N、`limit` 邊界 |
| 統計 | `/api/stats` 與排行榜資料一致 |
| 輸入安全 | 壞 JSON、陣列、超長名字、非法分數、16 KiB body 上限 |
| HTTP 行為 | 404、405 + `Allow`、HEAD 無 body、`no-store`、`nosniff` |
| CORS | `OPTIONS` preflight 回 204，允許 GitHub Pages 單檔版跨網域呼叫 |
| 靜態資產 | 首頁、`game.js`、`sw.js` 由 Static Assets 正確提供 |
| Service Worker | 確認 `sw.js` 會跳過 `/api/`，且版本已更新 |
| 單檔版 | `build:standalone` 能產生內嵌式 `index.html` |

完整輸出在 `tests/test-report.txt`。

### 為什麼不用瀏覽器 E2E？

HW7 已經有 6 個 Playwright E2E 測試，驗證遊戲操作、排行榜 UI、離線與手機版。HW9 的改動集中在後端平台轉移與 API 相容性，因此測試重心放在：

- Worker 的 HTTP 行為與 D1 整合；
- 前端沿用 HW7 已驗證過的遊戲程式，只改文案；
- 用 `wrangler dev` 實際啟動 Cloudflare 本機執行環境，而不是模擬函式。

若時間允許，下一步可以沿用 HW7 的 `tests/e2e/game.spec.js`，把 `baseURL` 指向 `wrangler dev` 或線上網址，補上跨平台 E2E。

---

## 12. 設計重點

### 平台轉移，不是重寫

- 保留 HW7 的前端與 API 契約，降低回歸風險。
- 只把「Python HTTP Server + SQLite」換成「Cloudflare Worker + D1」。
- 遊戲邏輯、Canvas、PWA、Service Worker 完全沿用。

### 安全性

- **SQL injection**：全部使用 D1 `bind()` 參數化查詢。
- **XSS**：前端排行榜使用 `textContent` 插入名字，不解析 HTML。
- **輸入驗證**：名字 1～16 個 Unicode 字元、分數 0～1,000,000 整數。
- **Body 大小**：Content-Length 與實際 bytes 都檢查，超過 16 KiB 回 413。
- **快取**：排行榜 API 不回快取；Service Worker 不快取 `/api/`。
- **最小權限**：Worker 只有 D1 與 Static Assets 兩個 binding，沒有多餘服務。

### 可觀測性

- `observability.enabled = true`，可在 Cloudflare 後台查看請求與 `console.error` 日誌。
- D1 失敗時回傳一致的 JSON 錯誤，不把內部錯誤細節暴露給使用者。

### 成本與部署

- 靜態檔案由 Cloudflare 邊緣節點提供，不需要自架 nginx。
- Worker 與 D1 都有免費方案，適合課程專案與小型作品。
- 不需要 Docker、VM、反向代理或 TLS 憑證管理。

---

## 13. HW7 與 HW9 的差異

| 項目 | HW7 | HW9 |
|---|---|---|
| 前端 | 原生 HTML／CSS／JS + Canvas | 沿用，僅改文案 |
| 伺服器 | Python `ThreadingHTTPServer` | Cloudflare Worker |
| 資料庫 | 本機 SQLite 檔案 | Cloudflare D1（SQLite 相容） |
| 靜態檔案 | Python 自製靜態伺服器 | Cloudflare Static Assets |
| 排行榜範圍 | 只能在執行後端的那台機器 | 全球同一個網址 |
| 部署 | 自己的電腦或 VM | `wrangler deploy` |
| 維運 | 需要開機、開 port、備份檔案 | Cloudflare 代管 |
| 測試 | 18 unit + 19 system + 6 E2E | 7 unit + 14 API 整合 + dry-run |
| 離線 | PWA + 本機最高分 | 相同，且排行榜 API 明確不快取 |
| API 契約 | `/api/health`、`/api/scores`、`/api/stats` | 相同，前端可直接重用 |

---

## 14. 已知限制

- **沒有帳號系統**：名字可以重複，任何人都能送出分數。
- **沒有防作弊**：前端可以任意送出 0～1,000,000 的分數。若要正式營運，應加入伺服器端驗證、簽章或重播驗證。
- **沒有速率限制**：公開排行榜可能被大量請求洗版；可加上 Cloudflare Rate Limiting、Turnstile 或 Durable Object 計數。
- **免費方案有限額**：Workers 請求數、D1 讀寫列數與儲存空間依 Cloudflare 官方免費方案為準；流量大時需升級。
- **temporary preview 有期限**：本次示範使用 temporary 帳號，claim URL 約 60 分鐘內有效；長期展示請用自己的帳號重新部署。
- **離線時沒有全球排行榜**：這是刻意設計，避免顯示過期資料；離線時只保留本機最高分。
- **尚未補跨瀏覽器 E2E**：目前以 API 整合測試與 HW7 現有 E2E 為基礎，尚未把 Playwright 指向 Cloudflare 版本。

---

## 15. 可以再往哪裡做

1. **防作弊與簽章**：用 Web Crypto 對每局結果簽章，或把遊戲邏輯搬到 Worker 驗證。
2. **Cloudflare Turnstile**：送出分數前加入人機驗證，降低機器人洗榜。
3. **Rate Limiting**：用 Cloudflare Rate Limiting binding 限制每個 IP 的送出頻率。
4. **Durable Objects**：做即時排行榜、線上觀戰或 WebSocket 更新。
5. **每週榜／好友榜**：在 D1 加入賽季欄位與排程清理。
6. **帳號系統**：接 Cloudflare Access、OAuth 或自製 JWT。
7. **CI/CD**：用 GitHub Actions 執行 `bash test.sh`，通過後 `wrangler deploy`。
8. **自訂網域**：在 Cloudflare Dashboard 綁定自己的網域，取代 `workers.dev`。
9. **E2E**：把 HW7 的 Playwright 測試指向 `wrangler dev` 或正式網址。

---

## 16. 參考資料

- Cloudflare Workers Static Assets：<https://developers.cloudflare.com/workers/static-assets/>
- Cloudflare D1：<https://developers.cloudflare.com/d1/>
- Wrangler 指令：<https://developers.cloudflare.com/workers/wrangler/>
- Workers 入門：<https://developers.cloudflare.com/workers/get-started/guide/>
- HW7 DINO RUN：`../HW7/README.md`

---

## 17. 快速指令摘要

```bash
# 本機開發
npm install
npm run db:migrate:local
npm run dev

# 測試
bash test.sh

# 產生單檔 HTML（GitHub Pages 用）
npm run build:standalone

# 自己的 Cloudflare 帳號部署
npx wrangler login
npx wrangler d1 create hw9-dino-run
# 將新的 database_id 填入 wrangler.jsonc
npm run db:migrate:remote
npm run deploy
```
