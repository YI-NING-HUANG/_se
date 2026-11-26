# 現代軟體工程作業總覽（HW1–HW11）

本文件把 HW1–HW10 整理成一份可直接閱讀的總覽，最後一節說明 HW11。
每個作業都使用獨立的章節，內含自己的簡介、功能、快速開始、測試結果與限制，
因此可以只讀其中一節，不需要先讀其他作業；需要更細的內容時，再點各節的
「原始文件」連結。

> 週次說明：repo 中沒有 `HW5` 資料夾，目錄依實際存在的作業編號排列。
> 所有路徑均相對於 repo 根目錄；指令若標示「在 HWx 資料夾執行」，請先 `cd homework/HWx`。

<a id="toc"></a>
## 目錄

| 週次 | 作業 | 主題 | 快速跳轉 | 原始文件 |
|---|---|---|---|---|
| 1 | HW1 | mycurl：類 curl 的 CLI | [前往](#hw1) | [HW1/README.md](../HW1/README.md) |
| 2 | HW2 | 校務系統 Web 應用（三個版本） | [前往](#hw2) | [HW2/README.md](../HW2/README.md) |
| 3 | HW3 | ForumKeep 公開論壇離線保存 | [前往](#hw3) | [HW3/README.md](../HW3/README.md) |
| 4 | HW4 | Git flow / GitHub flow 與 PR | [前往](#hw4) | [HW4/README.md](../HW4/README.md) |
| 5 | HW5 | 未提供（repo 中無此資料夾） | [前往](#hw5) | — |
| 6 | HW6 | Docker Compose 微服務系統 | [前往](#hw6) | [HW6/README.md](../HW6/README.md) |
| 7 | HW7 | DINO RUN 離線小恐龍 PWA | [前往](#hw7) | [HW7/README.md](../HW7/README.md) |
| 8 | HW8 | xfrescue XenForo 論壇備份 | [前往](#hw8) | [HW8/README.md](../HW8/README.md) |
| 9 | HW9 | DINO RUN on Cloudflare + D1 | [前往](#hw9) | [HW9/README.md](../HW9/README.md) |
| 10 | HW10 | cafeteria-sim 排隊模擬套件 | [前往](#hw10) | [HW10/README.md](../HW10/README.md) |
| 11 | HW11 | 作業總覽、PyPI 發佈與 AI 使用說明 | [前往](#hw11) | [本頁](README.md) |

> HW5：repo 中沒有對應資料夾，目錄保留一列並在下方以獨立章節說明。

---

<a id="hw1"></a>
## HW1：mycurl — 類 curl 的 CLI

| 項目 | 內容 |
|---|---|
| 週次 | 1 |
| 主題 | 用 Python 標準庫實作命令列 HTTP 客戶端 |
| 技術 | Python 3.8+、`urllib`、`ssl`、`argparse`、unittest、Bash |
| 進入點 | `homework/HW1/mycurl/mycurl.py`、`mycurl2.py` |
| 測試 | `test.sh`：PASS=14 FAIL=0（含 13 個單元測試） |
| 原始文件 | [HW1/README.md](../HW1/README.md) |

### 專案簡介

**mycurl** 是一個「最小可用版的 curl」：用純 Python 標準函式庫寫成的命令列 HTTP 客戶端。
給它 URL 和選項，它就發出 HTTP 請求，把伺服器回傳的內容印出來或存成檔案。
專案動機是把 curl 最常用的功能親手做出來，藉此理解 HTTP 請求／回應、命令列參數設計、
結束碼與輸出流等實務細節。

`mycurl2.py` 是 `mycurl.py` 的超集：直接沿用同一套核心（parser 繼承、共用 `do_request`），
再把結果包裝成網頁，方便展示與操作。

### 核心功能

- **請求方法**：`-X POST`；不指定時，有 `-d` 就是 POST，否則 GET。
- **自訂請求**：`-H "Key: Value"` 加標頭（可重複）；`-d "a=1"` 送資料，`@檔案` 從檔讀；
  `--json '{"a":1}'` 送 JSON 並自動加 Content-Type。
- **輸出控制**：預設 body 印到螢幕；`-o 檔名` 存檔；`-O` 用遠端檔名存檔；`-i` 連回應標頭一起顯示。
- **除錯與行為**：`-v` 顯示來往過程；`-L` 跟隨重新導向（另有 `--max-redirs`）；
  `--fail` 遇到 HTTP 錯誤回結束碼 22；`-s` 安靜模式。
- **認證與 TLS**：`-u` Basic 認證、`-A` User-Agent、`-k` 略過 SSL 驗證。
- **結束碼對齊 curl**：`0` 成功、`2` 參數錯誤、`7` 連線失敗、`22` HTTP 錯誤、
  `23` 寫檔失敗、`26` 讀檔失敗、`28` 逾時。

### 快速開始

在 repo 根目錄執行：

```bash
# 基本 GET
python homework/HW1/mycurl/mycurl.py https://example.com

# 加上標頭、顯示回應標頭、存檔
python homework/HW1/mycurl/mycurl.py -H "X-Token: abc" -i -o out.json https://httpbin.org/get

# 顯示請求過程
python homework/HW1/mycurl/mycurl.py -v https://httpbin.org/get
```

`mycurl2` 額外提供：

```bash
# 把回應包裝成 HTML 報告
python homework/HW1/mycurl/mycurl2.py -i https://example.com --html-out report.html

# 啟動本機網頁操作介面（只聽 127.0.0.1）
python homework/HW1/mycurl/mycurl2.py --serve 8080
# 開 http://127.0.0.1:8080/

# 產生專案介紹頁
python homework/HW1/mycurl/mycurl2.py --demo-out index.html
```

### 專案結構

```text
homework/HW1/mycurl/
  mycurl.py        # 主程式（約 309 行，核心）
  mycurl2.py       # 超集：import mycurl + --html-out/--serve/--demo-out
  index.html       # 介紹頁
  mycurl.html      # mycurl.py 原始碼瀏覽頁
  mycurl2.html     # mycurl2.py 原始碼瀏覽頁
  test.sh          # 一鍵檢測腳本
  test-report.txt  # 最新檢測紀錄
  tests/           # 13 個單元測試（本機 http.server，不需外網）
  README.md        # mycurl 詳細文件
```

### 測試與成果

```bash
bash homework/HW1/mycurl/test.sh 2>&1 | tee homework/HW1/mycurl/test-report.txt
```

最新結果：**PASS=14 FAIL=0，ALL CHECKS PASSED**，包含基本指令、13 個單元測試、
實機請求、兩支程式輸出一致性、`--html-out` 與 `--serve`。
完整過程見 `mycurl/test-report.txt`。

### 限制與備註

- 只支援 HTTP/HTTPS 基本功能，不處理 HTTP/2、cookie jar、multipart 上傳等進階功能。
- `-v` 全走 stderr，不污染 pipe 或存檔內容。
- body 以 bytes 寫入 stdout，圖片與二進位內容不會損壞。

[回目錄](#toc) ｜ [完整內容](../HW1/README.md) ｜ [線上展示](https://yi-ning-huang.github.io/_se/homework/HW1/mycurl/)

---

<a id="hw2"></a>
## HW2：校務系統 Web 應用（三個版本）

| 項目 | 內容 |
|---|---|
| 週次 | 2 |
| 主題 | 類似金門大學校務系統的選課 Web 應用 |
| 技術 | Python 標準庫、`sqlite3`、HTML/CSS/JS、Bash |
| 進入點 | `homework/HW2/app1/app.py`、`app2/`、`app3/` |
| 測試 | 三個版本皆 PASS=13 FAIL=0 |
| 原始文件 | [HW2/README.md](../HW2/README.md) |

### 專案簡介

以 Python 標準庫 + SQLite 實作選課系統，不需要 `pip install`。
專案採版本演進：每一版都有獨立資料夾、獨立測試與前一版回歸測試，
確保新增功能不會破壞選課核心。

> 個資聲明：本專案所有人名皆為虛構假名，與現實人物無關；
> 課程橫跨多系所，取材自綜合型大學常見開課。

### 版本對照

| 版 | 資料夾 | 測試入口 | 內容 | 結果 |
|---|---|---|---|---|
| v1.0 | `app1/` | `test/test.sh` | 選課核心：登入、課程查詢/搜尋、加選/退選、擋修（額滿/衝堂/學分上限/重複）、我的課表 | PASS=13 FAIL=0 |
| v1.1 | `app2/` | `test/test2.sh` | v1.0 + 我的成績（分數/等第/加權平均/GPA）+ `/api/grades`，含 v1.0 回歸 | PASS=13 FAIL=0 |
| v1.2 | `app3/` | `test/test3.sh` | v1.1 + 老師登分/改分 + 管理員開課，導覽按角色顯示，含回歸 | PASS=13 FAIL=0 |
| 展示 | `docs/` | — | 靜態展示頁；`python docs/build.py` 可重建 | 已產生 |

### 快速開始

在 repo 根目錄執行（以 v1.0 為例）：

```bash
python homework/HW2/app1/app.py --initdb
python homework/HW2/app1/app.py --serve 8080
# 開 http://127.0.0.1:8080/
# 帳號 s001、密碼 1234
```

免跑 server 也能看：雙擊 `homework/HW2/app1/index.html`。

一次跑完三個版本的回歸測試：

```bash
bash homework/HW2/test/test-all.sh
```

### 版本門檻

1. 每一版資料夾內都有自己的 `test.sh` + `test-report.txt`。
2. 該版 `bash test.sh` 出現 `ALL CHECKS PASSED` 才能凍結、複製開下一版。
3. 下一版 `test.sh` 必須包含上一版的回歸測試。

### 專案結構

```text
homework/HW2/
  app1/       # v1.0 選課核心
  app2/       # v1.1 成績與 GPA
  app3/       # v1.2 老師登分與管理員開課
  docs/       # 靜態展示頁（非版本）
  test/       # test.sh、test2.sh、test3.sh、test-all.sh
```

### 測試與成果

三個版本皆為 **PASS=13 FAIL=0，ALL CHECKS PASSED**。
測試分門別類收在 `test/`，`test-all.sh` 可一次全跑，詳見 `test/README.md`。

### 限制與備註

- 以教學與展示為目的，沒有正式的身分驗證、密碼雜湊或權限控管。
- 資料庫為本機 SQLite 檔案，不適合直接當成正式校務系統部署。

[回目錄](#toc) ｜ [完整內容](../HW2/README.md) ｜ [線上展示](https://yi-ning-huang.github.io/_se/homework/HW2/docs/)

---

<a id="hw3"></a>
## HW3：ForumKeep 公開論壇離線保存

| 項目 | 內容 |
|---|---|
| 週次 | 3 |
| 主題 | 公開、唯讀的論壇離線保存工具 |
| 技術 | Python 3.11+ 標準庫、SQLite、BFS 爬蟲、HTML/CSS 解析、靜態網站生成 |
| 進入點 | `python -m forumkeep`（在 HW3 資料夾執行） |
| 測試 | 36 個 unittest；端到端 `test.sh`：PASS=10 FAIL=0 |
| 原始文件 | [HW3/README.md](../HW3/README.md) |

### 專案簡介

ForumKeep 會沿著站內連結抓取公開頁面，收集文章中的圖片、附件、CSS、字型等素材，
最後產生一個可直接用瀏覽器打開的靜態離線網站，並保留原始 HTML 與素材雜湊。
設計目標是「不造成站方負擔、不繞過權限、中斷後可續傳」。

> 只適用於公開內容。使用前請確認站方規範、`robots.txt` 與著作權要求。
> 本工具不登入、不發文、不繞過權限，預設也不下載需要登入的頁面。

### 核心功能

- **禮貌爬取**：預設遵守 `robots.txt`、同一主機限速、可設定重試與逾時。
- **可續傳**：佇列、頁面、素材與錯誤都存在 SQLite；中斷後重跑會接續。
- **只讀保存**：不帶登入 cookie、不送出表單、不執行 JavaScript。
- **完整素材**：HTML、圖片、附件、壓縮檔、文件、CSS、字型、影音。
- **CSS 依賴探索**：下載 CSS 後繼續找 `url(...)` 與 `@import` 的圖片/字型。
- **SHA-256 命名**：素材以內容雜湊命名，可辨識重複內容。
- **離線網站**：重寫站內連結與素材路徑，產生首頁、頁面列表、版面列表、
  討論串列表、素材庫、全文搜尋與 manifest。
- **驗證與修復**：`verify` 檢查雜湊與檔案；`verify --fix` 把損壞項目重新排隊。
- **匯出**：可把 pages / assets / links 匯出成 JSONL 或 CSV。
- **零第三方依賴**：只需要 Python 3.11+。

### 快速開始

在 `homework/HW3` 資料夾執行：

```bash
# 1. 建立封存並記錄起始網址
python -m forumkeep init --url https://example.com/forum/ --out archive

# 2. 抓頁面（第一次可先用 --max-pages 50 試跑）
python -m forumkeep crawl --out archive --delay 1.5 --max-pages 500

# 3. 下載素材
python -m forumkeep download --out archive

# 4. 產生離線網站
python -m forumkeep build --out archive

# 5. 驗證
python -m forumkeep verify --out archive

# 6. 打開 archive/site/index.html
```

也可以一次跑完：

```bash
python -m forumkeep run \
  --url https://example.com/forum/ \
  --out archive \
  --delay 1.5 \
  --max-pages 500
```

本機範例論壇：

```bash
# 另開一個終端機
python -m http.server 8765 --directory examples/mini_forum

# 回到 HW3 資料夾
python -m forumkeep run \
  --url http://127.0.0.1:8765/ \
  --out demo \
  --delay 0 \
  --retries 1
```

### 輸出結構

```text
archive/
├── forumkeep.sqlite3          # 佇列、頁面、素材、連結、錯誤、設定
├── README.txt                 # 封存說明
├── raw/pages/                 # 原始 HTML
├── blobs/ab/                  # SHA-256 命名的素材 blob
├── site/
│   ├── index.html             # 離線首頁
│   ├── pages.html             # 所有頁面
│   ├── forums.html            # 版面
│   ├── threads.html           # 討論串
│   ├── assets.html            # 素材庫
│   ├── search.html            # 全文搜尋
│   ├── search-index.js
│   ├── manifest.json
│   ├── pages/<host>/          # 離線頁面
│   └── assets/<sha-prefix>/   # 離線素材
└── exports/                   # export 指令的輸出（若有執行）
```

### 測試與成果

在 `homework/HW3` 執行：

```bash
bash test.sh
```

結果：

```text
Ran 36 tests ... OK
結果: PASS=10 FAIL=0
ALL CHECKS PASSED
```

測試涵蓋 HTML 解析、robots、policy、store、下載、爬取、建站，
並啟動本機 `examples/mini_forum` 實際跑 `run` → `status` → `verify`。
測試只連線到本機隨機 port，不需要外部網路。

### 實際場域測試

HW3 曾對 RPG Maker Web 論壇做低量觀測。該站 `robots.txt` 對一般爬蟲全面
`Disallow: /`，因此 ForumKeep 預設的 `respect` 模式回報 blocked、抓取 0 頁。
這是工具預期的正確行為，不是程式錯誤；專案也沒有使用 `--robots ignore` 強行繞過。

### 限制與備註

- 不執行 JavaScript，純前端動態載入的內容不會被發現。
- 不處理登入、會員、私訊、投票、發文等互動功能。
- CSS 解析是輕量實作，不保證涵蓋所有 CSS 語法。
- 預設只抓與種子同主機的素材；跨網域 CDN 需明確設定。
- 不是 WARC 工具；原始 HTML 與素材分開保存，離線網站是另外產生的。

[回目錄](#toc) ｜ [完整內容](../HW3/README.md)

---

<a id="hw4"></a>
## HW4：Git flow / GitHub flow 與 Pull Request

| 項目 | 內容 |
|---|---|
| 週次 | 4 |
| 主題 | Forking Workflow、功能分支、merge 與 Pull Request |
| 技術 | Git、GitHub、Markdown |
| 成果 | 已建立 PR #1，完整記錄 branch、merge、reflog 與 PR 流程 |
| 原始文件 | [HW4/README.md](../HW4/README.md) |

### 專案簡介

本作業不是應用程式，而是 Git 協作流程的實作紀錄。採用 **GitHub Flow / Forking Workflow**：

1. 母專案只保留穩定的 `main`。
2. 開發者在自己的 fork 開功能分支 `developGitBranch` 做事。
3. 做完在 fork 內 merge 回 fork 的 `main` 驗證，再從 fork 發 Pull Request
   回母專案的 `main`，等母專案維護者審查合併。

### 流程與指令

```bash
# 1. 在 GitHub 網頁 fork 母專案後，clone 自己的 fork
git clone https://github.com/leiuyushi0401-cpu/se_example.git
cd se_example

# 2. 建立功能分支
git checkout -b developGitBranch

# 3. 在分支上修改、commit、push
git add -A
git commit -m "Add README explaining Git workflow"
git push origin developGitBranch

# 4. 合併回 fork 的 main
git checkout main
git merge developGitBranch
git push origin main
```

本次 merge 為 **Fast-forward**，fork 的 `main` 與 `developGitBranch` 都指向
`004c1a0`。`git reflog` 完整記錄 checkout 與 merge 過程。

### Pull Request

在 GitHub 上設定：

- `base: YI-NING-HUANG/se_example:main`
- `head: leiuyushi0401-cpu/se_example:main`

建立後產生 PR #1（Open 狀態），等母專案擁有者按下 `Merge pull request`
才會真正寫入母專案。

### 相關連結

- 母專案：<https://github.com/YI-NING-HUANG/se_example/commits/main/>
- 功能分支：<https://github.com/leiuyushi0401-cpu/se_example/commits/developGitBranch>
- 子專案（fork）：<https://github.com/leiuyushi0401-cpu/se_example/commits/main/>
- Pull Request：<https://github.com/YI-NING-HUANG/se_example/pull/1>

### 成果與備註

- 完成 fork、分支、commit、merge、push 與 PR 的完整流程。
- 此作業沒有程式碼，重點在流程紀錄與指令可重現性。
- 參考資料包含 Git 官方文件、GitHub Docs 與阮一峰的 Git 工作流程文章。

[回目錄](#toc) ｜ [完整內容](../HW4/README.md)

---

<a id="hw5"></a>
## HW5：未提供

repo 中沒有 `HW5` 資料夾，因此本總覽不列 HW5 章節。
後續的 HW6–HW10 依實際存在的資料夾編號整理。

[回目錄](#toc)

---

<a id="hw6"></a>
## HW6：Docker Compose 微服務系統

| 項目 | 內容 |
|---|---|
| 週次 | 6 |
| 主題 | nginx + Node.js + Python + Rust + PostgreSQL 的微服務系統 |
| 技術 | Docker、Docker Compose、nginx、Node.js、Flask、Rust Axum、PostgreSQL 16 |
| 進入點 | `homework/HW6/docker-compose.yml` |
| 成果 | 5 個服務啟動，API 與資料庫 CRUD 實測通過 |
| 原始文件 | [HW6/README.md](../HW6/README.md) |

### 專案簡介

以 Docker Compose 建置的迷你微服務系統，附一個可直接操作的 Web 介面，
用來展示服務狀態、資料庫 CRUD 與各後端服務。
對外只開放 nginx 的 `8080`，其餘服務僅在 Compose 內部網路互通。

### 系統架構

```text
                     Browser
                        │  http://localhost:8080
                        ▼
              ┌──────────────────┐
              │      nginx       │  web server + reverse proxy
              │   (nginx:alpine) │
              └────────┬─────────┘
                       │ Compose 內部網路（服務名稱即 DNS）
       ┌───────────────┼────────────────┬─────────────────┐
       │               │                │                 │
       ▼               ▼                ▼                 ▼
   / 靜態頁面      /api/*           /python/*          /rust/*
 frontend/      backend-node       backend-python     backend-rust
 index.html        :3000              :5000              :8000
                    │                                     │
                    ▼                                     │
              ┌───────────┐                               │
              │    db     │  PostgreSQL 16                │
              │  :5432    │  services / notes             │
              └───────────┘                               │
                    ▲                                     │
                    └──── backend-node 聚合查詢各服務 ────┘
```

### 服務一覽

| 服務 | 映像 / 語言 | 功能 | 對外路徑 |
|---|---|---|---|
| nginx | `nginx:alpine`（自建） | Web server + Reverse Proxy | `http://localhost:8080/` |
| backend-node | `node:20-alpine`（自建） | 主 API、聚合狀態、Notes CRUD | `/api/health`、`/api/status`、`/api/notes`、`/api/services` |
| backend-python | `python:3.12-slim`（自建） | Flask 運算服務 | `/python/api/health`、`/python/api/info`、`/python/api/compute` |
| backend-rust | `rust:1.82-slim-bookworm` → `debian:bookworm-slim`（多階段） | Axum 高效能 fib 服務 | `/rust/api/health`、`/rust/api/hello`、`/rust/api/fib?n=30` |
| db | `postgres:16-alpine`（官方） | 關聯式資料庫 | 僅內部 `db:5432` |

### 快速開始

在 `homework/HW6` 資料夾執行：

```bash
docker compose up -d --build
docker compose ps
```

開啟 <http://localhost:8080/> 可以看到系統架構、服務健康狀態、
PostgreSQL 留言板、Python 運算、Rust fib 與服務清單。

驗證 API：

```bash
curl http://localhost:8080/nginx-health
curl http://localhost:8080/api/status
curl http://localhost:8080/python/api/health
curl http://localhost:8080/rust/api/health

curl -X POST http://localhost:8080/api/notes \
  -H "Content-Type: application/json" \
  -d '{"content":"docker compose verification","author":"tester"}'

curl "http://localhost:8080/rust/api/fib?n=30"
```

常用維運指令：

```bash
docker compose logs -f
docker compose logs -f backend-node
docker compose restart nginx
docker compose exec db psql -U hw6user -d hw6db -c "SELECT * FROM notes;"
docker compose down
docker compose down -v   # 連同 pgdata 資料卷一起刪除
```

### 專案結構

```text
HW6/
├── docker-compose.yml          # 5 個服務的編排定義
├── .dockerignore
├── db/init.sql                 # services、notes 兩張表 + 種子資料
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf              # 靜態網頁 + 反向代理
├── frontend/index.html         # Web 展示介面
├── backend-node/
│   ├── Dockerfile
│   ├── package.json
│   └── server.js               # health/status、notes CRUD、services
├── backend-python/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                  # Flask：health/info/compute
└── backend-rust/
    ├── Dockerfile              # 多階段建置
    ├── Cargo.toml
    └── src/main.rs             # Axum：health/hello/fib
```

### 測試與成果

實際啟動結果：`db` 為 healthy，`nginx`、`node`、`python`、`rust` 皆為 Up；
`/api/status` 回報 `postgres`、`python`、`rust` 依賴皆為 `ok`。
Notes CRUD、Python factorial/fibonacci、Rust fib 與 nginx health 都已用 curl 實測。

### 限制與備註

- `init.sql` 只在 `pgdata` 首次初始化時執行；修改 SQL 後需 `docker compose down -v` 重建。
- `proxy_pass` 結尾有無 `/` 會改變轉發路徑，設定時需注意。
- 若 `8080` 被占用，可修改 compose 的埠映射，例如 `"8090:80"`。
- 此為教學與展示用系統，沒有正式的使用者認證與 TLS 設定。

[回目錄](#toc) ｜ [完整內容](../HW6/README.md)

---

<a id="hw7"></a>
## HW7：DINO RUN 離線小恐龍 PWA

| 項目 | 內容 |
|---|---|
| 週次 | 7 |
| 主題 | Canvas 無限跑酷遊戲 + SQLite 排行榜 + PWA 離線遊玩 |
| 技術 | HTML/CSS/JavaScript、Canvas、Service Worker、Python 標準庫、SQLite、Playwright |
| 進入點 | `homework/HW7/app.py` |
| 測試 | 18 單元 + 19 系統 + 6 E2E = 43 passed |
| 原始文件 | [HW7/README.md](../HW7/README.md) |

### 專案簡介

以 Google Chrome 斷線小恐龍為靈感實作的無限跑酷遊戲。
前端使用原生 HTML／CSS／JavaScript + Canvas，沒有框架、CDN、外部圖片或音檔；
後端使用 Python 3 標準庫 `ThreadingHTTPServer` + SQLite 提供靜態檔案與排行榜 API；
Service Worker + PWA manifest 讓遊戲第一次載入後可離線遊玩。

### 核心功能

- **核心玩法**：小恐龍自動向前跑，玩家跳躍與蹲下閃避障礙物；碰撞即結束，可立即重來。
- **障礙物**：仙人掌有小／大、單株／叢生；分數超過 240 後出現高、中、低翼龍。
- **分數與難度**：分數為 `floor(距離 / 10)`；速度從 360 px/s 線性增加到 820 px/s。
- **畫面變化**：每 700 分切換白天／夜晚，含雲朵、星空、地面細節與粒子效果。
- **音效**：Web Audio 即時合成，可開關，不需要外部音檔。
- **最高分**：個人最高分存在 `localStorage`，重新整理或離線都不會消失。
- **SQLite 排行榜**：遊戲結束後可輸入 1～16 字名字；排行榜顯示 Top 10、總場次、
  最高分與平均分。
- **PWA 離線**：Service Worker 快取 App Shell；`/api/` 不進快取，避免舊資料。
- **手機支援**：響應式版面、點擊跳躍、JUMP／DUCK 觸控按鈕。
- **安全**：限制 body 大小、驗證名字與分數、參數化 SQL、阻擋路徑穿越。

### 快速開始

在 `homework/HW7` 資料夾執行：

```bash
python app.py
# 開 http://127.0.0.1:8787/
```

常用參數：

```bash
python app.py --host 0.0.0.0 --port 8787
python app.py --db data/scores.db
```

第一次啟動會自動建立 `data/scores.db`，不需要手動建表。

### 操作方式

| 操作 | 按鍵／方式 |
|---|---|
| 開始／跳躍 | `Space`、`↑`、`W`、點擊畫面、JUMP 按鈕 |
| 蹲下 | `↓`、`S`、按住 DUCK 按鈕 |
| 暫停／繼續 | `P`、`Esc`、畫面下方「暫停」按鈕 |
| 重新開始 | 遊戲結束後按 `Space`、`R` 或「再玩一次」 |
| 音效開關 | `M` 或右上角音效按鈕 |

### API

| Method | Path | 說明 |
|---|---|---|
| `GET` | `/api/health` | 健康檢查 |
| `GET` | `/api/scores?limit=10` | Top N 排行榜（`limit` 1～50）與統計 |
| `POST` | `/api/scores` | 新增分數，JSON：`{"name":"Dino","score":123}` |
| `GET` | `/api/stats` | 總場次、最高分、平均分 |

```bash
curl http://127.0.0.1:8787/api/health
curl "http://127.0.0.1:8787/api/scores?limit=5"
curl -X POST http://127.0.0.1:8787/api/scores \
  -H "Content-Type: application/json" \
  -d '{"name":"Dino","score":321}'
```

### 專案結構

```text
HW7/
├─ app.py                  # Python 標準庫 HTTP server + SQLite + API
├─ test.sh                 # 一鍵測試（單元 + 系統 + E2E + JS 語法）
├─ data/scores.db          # 執行後自動產生（不進版控）
├─ static/
│  ├─ index.html           # 遊戲頁與排行榜介面
│  ├─ style.css
│  ├─ game.js              # Canvas 遊戲主程式
│  ├─ sw.js                # Service Worker（離線快取）
│  ├─ manifest.webmanifest
│  └─ icon.svg
└─ tests/
   ├─ unit/test_core.py    # 18 個 server 核心單元測試
   ├─ system/test_api.py   # 19 個 HTTP／Web API 系統測試
   ├─ e2e/game.spec.js     # 6 個 Playwright E2E 測試
   ├─ run_tests.sh
   └─ test-report.txt
```

### 測試與成果

在 `homework/HW7` 執行：

```bash
bash test.sh
```

結果：

- 單元測試：**18 passed**
- 系統測試：**19 passed**
- E2E 測試：**6 passed**
- JavaScript 語法檢查：**OK**
- 總結：**ALL CHECKS PASSED**（合計 43 個測試通過）

測試隔離方式：單元測試使用暫存 DB；系統測試使用暫存目錄與隨機埠；
E2E 使用 `.tmp/e2e.db`，不影響正式資料。

### 限制與備註

- 排行榜需要後端；只把 `static/` 放到 GitHub Pages 時只有遊戲與離線功能。
- 沒有帳號系統，名字可重複，排行榜是公開的。
- 音效受瀏覽器自動播放政策限制，需要先有使用者互動才會發聲。
- E2E 目前只使用系統 Chrome，尚未涵蓋 Firefox、Safari 或跨作業系統矩陣。

[回目錄](#toc) ｜ [完整內容](../HW7/README.md)

---

<a id="hw8"></a>
## HW8：xfrescue XenForo 論壇備份

| 項目 | 內容 |
|---|---|
| 週次 | 8 |
| 主題 | XenForo 論壇（RPG Maker Web）關站前公開內容備份 |
| 技術 | Python 3.11+ 標準庫、SQLite、HTML 解析、Docker |
| 進入點 | `python -m xfrescue`（在 HW8 資料夾執行） |
| 測試 | 27 個 unittest，全部使用本機 mock server |
| 原始文件 | [HW8/README.md](../HW8/README.md) |

### 專案簡介

`xfrescue` 是一套用 Python 標準庫寫成的 XenForo 論壇備份工具，
目標是保存 RPG Maker Web 論壇（`forums.rpgmakerweb.com`）在唯讀與關站前的公開內容。
它會抓取討論串、文章、作者、時間、原始 HTML、附件與外部檔案，
最後產生可離線瀏覽的靜態網站。所有進度都存在 SQLite，中斷後重跑同一道命令即可續傳。

官方論壇的 `robots.txt` 對一般爬蟲全面 `Disallow: /`，因此工具預設 `--robots respect`
會拒絕下載被 disallow 的 URL；此限制沒有被繞過。HW8 改用混合來源：

1. 社群 archive API（`rpgmakerchat.com`）取得文章文字、作者、時間與 asset URL。
2. 官方論壇 live HTML（可選）取得原始頁面與 archive API 未收錄的內容。
3. 下載器負責附件、圖片、壓縮檔、GitHub raw 等檔案，含 rate limit、重試、
   SHA-256 去重與續傳。
4. 靜態網站產生器把資料變成離線 HTML。

### 核心功能

- **討論串與文章**：記錄作者、樓層、時間、原始 HTML、純文字與 URL。
- **附件與外部檔案**：XenForo 附件優先，GitHub `blob` 自動改寫成 `raw`；
  區分「檔案主機頁」與 CDN 直連檔，避免把 HTML 存成假 ZIP。
- **續傳**：所有進度存在 SQLite，中斷後重跑同一道命令即可接續。
- **去重與驗證**：同一份內容只存一次（SHA-256），`verify` 可檢查檔案雜湊。
- **離線網站**：重建討論串分頁（50 篇/頁）、forum 頁、素材 CSV 與 manifest。
- **全文搜尋**：`search.json` 同時索引 thread 與 post，post 結果直接跳到 `#post-ID`。
- **Docker**：內建 `Dockerfile` 與 `docker-compose.yml`。

### 快速開始

在 `homework/HW8` 資料夾執行：

```bash
python -m xfrescue --out archive init
python -m xfrescue --out archive discover --thread 183984
python -m xfrescue --out archive download --kind attachment
python -m xfrescue --out archive build
```

開啟 `archive/site/index.html`。

備份插件與資源 forum：

```bash
python -m xfrescue --out archive discover --preset plugins --with-posts
python -m xfrescue --out archive --robots warn download
python -m xfrescue --out archive build
```

Docker：

```bash
docker build -t xfrescue .
docker run --rm -v "%cd%/archive:/data" xfrescue --out /data/archive init
```

### 指令一覽

| 指令 | 用途 |
|---|---|
| `init` | 建立 archive 目錄與 SQLite |
| `list-forums` | 列出已知 forum；`--refresh` 重新抓取 |
| `discover` | 探索 thread/forum、文章與 asset URL |
| `download` | 下載 pending asset；可限 kind/host/數量 |
| `build` | 產生離線靜態網站 |
| `status` | 顯示 counts、bytes、錯誤 |
| `verify` | 檢查檔案 hash；`--fix` 把壞檔重設為 pending |
| `export` | 匯出 forums/threads/posts/assets 為 JSONL 或 CSV |

### 已完成範例

`demo/` 是目標公告串的實際備份：

- 273 posts，全部進入離線全文搜尋索引
- 18/26 assets 已下載（1.8 MB）
- 7 個外部圖片仍為 pending
- 1 個 link-only 外部頁面
- 已產生 `demo/site/index.html` 與討論串頁面

另以 forum 28（General Resources）實測：3 個討論串、817 篇文章、260 個 asset 參照，
成功下載 2 個論壇附件與 2 個 Flickr 圖片，SHA-256 驗證 4/4 通過。

### 專案結構

```text
xfrescue/
  cli.py          # argparse 入口
  db.py           # SQLite schema 與 Store
  net.py          # HTTP、rate limit、robots、重試
  classify.py     # URL/asset 分類、GitHub blob -> raw
  archive_api.py  # rpgmakerchat API
  live.py         # XenForo HTML parser
  download.py     # 下載、hash、去重、verify
  build.py        # 靜態網站產生器
  extract.py      # HTML link/asset 抽取與改寫
  tests/          # unittest + mock server
  Dockerfile
  docker-compose.yml
```

### 測試與成果

在 `homework/HW8` 執行：

```bash
python -m unittest discover -s tests -v
```

目前 27 個測試，涵蓋分類、HTML parser、archive API、下載、robots 阻擋、
SQLite、builder 與全文搜尋索引，全部使用本機 mock server，不需要網路。

驗證已下載檔案：

```bash
python -m xfrescue --out archive verify
python -m xfrescue --out archive verify --fix
```

### 與 HW3 的差異

| 面向 | HW3 ForumKeep | HW8 xfrescue |
|---|---|---|
| 入口 | 任意 seed URL，沿站內連結 BFS | forum/thread ID、preset（plugins/resources/assets/everything） |
| 主要來源 | live HTML 爬取 | 社群 archive JSON API；live XenForo HTML 可選 |
| 資料單位 | page / queue / link / alias | forum / thread / post |
| 資源判定 | 通用副檔名＋CSS 依賴 | XenForo 附件優先、GitHub blob→raw、檔案主機頁 vs CDN 直連 |
| 離線輸出 | 重寫原始頁面 | 重建討論串分頁、forum 頁、素材 CSV |
| 搜尋 | 頁面級 | thread＋post 級，直接跳到 `#post-ID` |
| 交付 | mini_forum＋test.sh E2E | 真實 273 篇 demo＋forum 28 實測＋Docker |

### 限制與備註

- Live HTML parser 只針對目前 XenForo 版型，站方改版可能需要更新 selector。
- JS-only 嵌入（例如部分 itch.io/YouTube 預覽）只保留連結，不保證可離線播放。
- 不是 WARC；這是「可閱讀的靜態備份」，不是像素級完整 replay。
- 需要登入才看得到的附件不會被下載；這是刻意設計。
- 全站 crawl 規模很大，建議先從 `--preset plugins` 或單一 forum 開始。

[回目錄](#toc) ｜ [完整內容](../HW8/README.md)

---

<a id="hw9"></a>
## HW9：DINO RUN on Cloudflare（Workers + D1）

| 項目 | 內容 |
|---|---|
| 週次 | 9 |
| 主題 | 把 HW7 的小恐龍搬到 Cloudflare，排行榜上雲 |
| 技術 | Cloudflare Workers、Static Assets、D1、Wrangler、JavaScript |
| 進入點 | `homework/HW9/`（`npm run dev`） |
| 測試 | 22 個測試（7 unit + 15 API/整合），PASS=22 FAIL=0 |
| 原始文件 | [HW9/README.md](../HW9/README.md) |

### 專案簡介

HW9 延續 HW7 的 DINO RUN，把「Python `ThreadingHTTPServer` + 本機 SQLite」
換成「Cloudflare Worker + D1」，其餘前端與 API 契約盡量沿用：

- **保留 HW7 的成果**：Canvas 遊戲、`style.css`、`index.html`、Service Worker、
  PWA manifest 全部沿用。
- **補上 HW7 的缺口**：排行榜不再需要自己開伺服器，任何人打開同一網址都會看到
  同一份全球排行榜。
- **保持 API 相容**：`/api/health`、`/api/scores`、`/api/stats` 與 HW7 格式一致。
- **增加分享方式**：除 Cloudflare 完整版，還能產生單檔 HTML 放到 GitHub Pages。

### 系統架構

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
```

> 名詞區分：**Cloudflare Worker** 是跑在 Cloudflare 邊緣網路上的伺服器端程式；
> **Service Worker** 是瀏覽器裡的離線快取代理。兩者名字很像，但完全不同。

### 核心功能

- 無限跑酷、仙人掌與翼龍、速度與分數、晝夜變化、Web Audio 音效、手機觸控。
- 遊戲結束後可輸入 1～16 字名字，把分數送到 Cloudflare D1。
- 排行榜顯示 Top 10、總場次、最高分、平均分；同分時先送出的人排名較前。
- API 使用 `ORDER BY score DESC, id ASC`，並以參數化查詢計算排名。
- 排行榜不快取（`Cache-Control: no-store`），避免看到過期結果。
- 輸入驗證、16 KiB body 上限、SQL injection 防護、XSS 防護、CORS。
- 單檔 HTML 版可放 GitHub Pages，透過 CORS 呼叫同一個 Worker API。

### 本機開發

在 `homework/HW9` 資料夾執行：

```bash
npm install
npm run db:migrate:local
npm run dev
# 開 http://localhost:8787/
```

常用指令：

| 指令 | 作用 |
|---|---|
| `npm run dev` | 套用本機 migration 並啟動 `wrangler dev` |
| `npm run db:migrate:local` | 對本機 D1 套用 `migrations/` |
| `npm run db:migrate:remote` | 對雲端 D1 套用 migration（部署前） |
| `npm run deploy` | `wrangler deploy` 部署到 Cloudflare |
| `npm test` | 執行 `bash test.sh` 全套測試 |

### 部署到自己的 Cloudflare 帳號

```bash
npx wrangler login
npx wrangler d1 create hw9-dino-run
# 將輸出的 database_id 填進 wrangler.jsonc
npm run db:migrate:remote
npm run deploy
```

部署後可用以下指令驗證：

```bash
curl https://你的-worker.workers.dev/api/health
curl https://你的-worker.workers.dev/api/scores
```

沒有帳號也可使用 Wrangler temporary preview 帳號展示，但約 60 分鐘後失效；
長期展示請照正式步驟部署到自己的帳號。

### 單檔 HTML 分享版

```bash
npm run build:standalone
```

產生 `HW9/index.html`（約 44 KB），內含遊戲 HTML、CSS、JavaScript、data URI 圖示，
並連回同一個 Cloudflare Worker + D1。可放到 GitHub Pages 或任何靜態空間。

### API 規格

| Method | Path | 說明 |
|---|---|---|
| `GET` | `/api/health` | 回報 Workers + D1 健康狀態 |
| `GET` | `/api/scores?limit=10` | Top N 排行榜與統計（`limit` 1～50） |
| `GET` | `/api/stats` | 總場次、最高分、平均分 |
| `POST` | `/api/scores` | 新增分數，成功回 `201 Created` 與排名 |

錯誤狀態：`400` 格式／範圍錯誤、`404` 未知 API、`405` 方法不支援、
`413` body 超過 16 KiB、`500` D1 失敗。所有 API 回應帶有
`Cache-Control: no-store` 與 `X-Content-Type-Options: nosniff`。

### 專案結構

```text
HW9/
├── index.html                    # 單檔分享版（由 build:standalone 產生）
├── package.json
├── wrangler.jsonc                # Worker、Static Assets、D1 綁定
├── scripts/build-standalone.mjs  # 把 public/ 內嵌成單一 index.html
├── migrations/0001_init.sql      # scores 資料表與排名索引
├── src/index.js                  # Cloudflare Worker API
├── public/                       # 由 Static Assets 託管
│   ├── index.html
│   ├── style.css
│   ├── game.js
│   ├── sw.js
│   ├── manifest.webmanifest
│   └── icon.svg
└── tests/
    ├── unit/validation.test.js   # 7 個純函式單元測試
    ├── api/api.test.js           # 15 個 HTTP + D1 整合測試
    └── test-report.txt
```

### 測試與成果

在 `homework/HW9` 執行：

```bash
bash test.sh
# 或 npm test
```

目前結果：

```text
測試案例：22（PASS=22 FAIL=0）
測試步驟：PASS=7 FAIL=0
ALL CHECKS PASSED
```

`test.sh` 會檢查 JS 語法、套用本機 D1 migration、清空測試資料庫、
執行 `wrangler deploy --dry-run`、產生單檔 HTML、啟動 `wrangler dev`，
再跑單元測試與真實 HTTP + D1 整合測試。

### 與 HW7 的差異

| 項目 | HW7 | HW9 |
|---|---|---|
| 伺服器 | Python `ThreadingHTTPServer` | Cloudflare Worker |
| 資料庫 | 本機 SQLite 檔案 | Cloudflare D1（SQLite 相容） |
| 靜態檔案 | Python 自製靜態伺服器 | Cloudflare Static Assets |
| 排行榜範圍 | 只能在執行後端的那台機器 | 全球同一個網址 |
| 部署 | 自己的電腦或 VM | `wrangler deploy` |
| 測試 | 18 unit + 19 system + 6 E2E | 7 unit + 15 API/整合 + dry-run |
| API 契約 | `/api/health`、`/api/scores`、`/api/stats` | 相同 |

### 限制與備註

- 沒有帳號系統與防作弊；前端可任意送出 0～1,000,000 的分數。
- 沒有速率限制；公開排行榜可能被大量請求洗版。
- 免費方案有限額，流量大時需升級。
- temporary preview 有期限；長期展示請用自己的帳號重新部署。
- 離線時沒有全球排行榜，只保留本機最高分（刻意設計）。
- 尚未把 Playwright E2E 指向 Cloudflare 版本。

[回目錄](#toc) ｜ [完整內容](../HW9/README.md) ｜ [GitHub Pages 單檔版](https://yi-ning-huang.github.io/_se/homework/HW9/)

---

<a id="hw10"></a>
## HW10：cafeteria-sim 排隊模擬套件

| 項目 | 內容 |
|---|---|
| 週次 | 10 |
| 主題 | 學餐排隊的離散事件模擬與最低成本人力配置 |
| 技術 | Python 3.10+、SimPy、argparse、unittest、setuptools、PyPI |
| 進入點 | `cafeteria-sim`（`homework/HW10`） |
| 測試 | 35 個 unittest；`test.sh`：PASS=14 FAIL=0；已發佈 PyPI 0.1.1 |
| 原始文件 | [HW10/README.md](../HW10/README.md) |

### 專案簡介

用 **SimPy** 建立的學餐排隊**離散事件模擬（DES）**套件。
它模擬尖峰時段的多個點餐窗口、共用或分開的取餐動線、顧客不耐煩離開，
並用模擬結果比較「多開一個窗口」能減少多少等候時間，
最後在等候目標下找出最低成本的人力配置。

- 套件名稱：`cafeteria-sim`
- Python 模組：`cafeteria_sim`
- 執行環境：Python 3.10+
- 執行期依賴：`simpy>=4.1,<5`
- 授權：MIT

### 安裝

```bash
pip install cafeteria-sim
cafeteria-sim demo
```

專案頁面：<https://pypi.org/project/cafeteria-sim/>

從原始碼安裝：

```bash
cd homework/HW10
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"   # macOS / Linux
```

### 命令列用法

單一情境：

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

比較加開窗口：

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

實際輸出重點：

- 只有 1 個窗口時容量約 48 人/小時，遠低於 120 人到達率，平均等候超過 1.5 小時。
- 3 個窗口時容量已足夠，平均總等候約 165 秒；取餐區成為下一個瓶頸。
- 4、5 個窗口的邊際效益快速下降，窗口使用率掉到 62%、47%。

最低成本人力配置：

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

最佳解不是等候最短的方案，而是在**滿足等候目標**的前提下成本最低的方案。
若目標太嚴苛、超過搜尋上限，指令會回傳非零結束碼並列出等候最短的候選方案。

### Python API

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

### 模型與指標

- 顧客以 Poisson 過程到達（指數分布間隔），到達率以「人/小時」設定。
- 服務時間分布可選 `exponential`、`deterministic`、`uniform`、`triangular`。
- 點餐窗口：每個窗口 capacity 1，顧客加入最短的窗口隊伍。
- 取餐模式：`shared`（共用取餐區）、`per_window`（每個窗口自己的取餐線）、
  `none`（只看點餐瓶頸）。
- 排隊上限可模擬 balk；耐心時間可模擬 renege。
- 暖機期間的顧客影響系統狀態，但不列入統計。
- 每次模擬使用固定 seed；多次 replication 使用 `seed, seed+1, ...`。
- 情境比較使用 common random numbers，降低不同情境之間的隨機差異。

主要指標：`arrivals`、`served`、`departures`、`abandoned`、`balked`、
`reneged_order`、`reneged_pickup`、`completion_rate`、`throughput_per_hour`、
`total_wait_*`、`system_time_*`、`*_utilization`、`avg_*_queue`、`max_*_queue`、`p95`。

### 專案結構

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
├── examples/quickstart.py
├── tests/                  # test_cli/config/distributions/metrics/optimization/simulation
├── tash.sh/                # 測試入口、報告、artifacts
├── LICENSE
├── pyproject.toml
├── test.sh
└── README.md
```

### 測試、打包與發佈

在 `homework/HW10` 執行：

```bash
bash test.sh
# 或 bash tash.sh/test.sh
```

目前已驗證：

- `test.sh`：**PASS=14 FAIL=0**，報告在 `tash.sh/test-report.txt`。
- 35 個 unittest 全數通過。
- `python -m build` 成功產生 `cafeteria_sim-0.1.1.tar.gz` 與
  `cafeteria_sim-0.1.1-py3-none-any.whl`。
- `twine check` 通過。
- wheel 安裝到乾淨虛擬環境後，`cafeteria-sim demo` 可正常執行。
- 已發佈至 PyPI 0.1.1：<https://pypi.org/project/cafeteria-sim/>

### AI 使用說明摘要

HW10 的 README 第 12 節（同步顯示於 PyPI 專案頁）提供給 AI 助手使用的完整說明，
重點包括：

- 先確認單位：到達率是人/小時、服務時間是秒、模擬長度是分鐘。
- 等候指標是 `total_wait_*`（只含排隊）；`system_time_*` 才是從到達至離開的總時間。
- 若 `completion_rate < 1`，要說明是 balk 還是 renege 造成。
- 變更窗口數或人力時，使用相同 seed（common random numbers）以降低比較噪聲。
- 正式結論建議 `replications >= 3`，並報告變異。
- 不要捏造套件未提供的參數或指標；需要新功能時明確說「目前不支援」。

驗證 AI 產生的程式：

```bash
python -m unittest discover -s tests -v
python -m cafeteria_sim run --json --seed 42
```

### 限制與備註

- 菜單只有一種服務時間分布，沒有區分不同餐點的差異。
- 顧客以最短隊伍選擇窗口，沒有考慮品牌偏好或熟客動線。
- 耐心時間固定用指數分布，尚未支援常數或歷史資料擬合。
- 假設人力在模擬期間固定，不處理輪班、休息與跨時段人力調整。
- 模擬結果為隨機估計；正式決策建議增加 `replications` 並報告信賴區間
  （目前輸出平均值與百分位，未提供信賴區間）。

[回目錄](#toc) ｜ [完整內容](../HW10/README.md) ｜ [PyPI 套件頁](https://pypi.org/project/cafeteria-sim/)

---

<a id="hw11"></a>
## HW11：作業總覽、PyPI 發佈與 AI 使用說明

| 項目 | 內容 |
|---|---|
| 週次 | 11 |
| 主題 | 將 HW1–HW10 整理成獨立可讀的總覽，並完成套件發佈與 AI 使用說明 |
| 技術 | Markdown、Git、PyPI、twine |
| 成果 | 本文件；`cafeteria-sim` 0.1.1 已發佈，PyPI 頁面含 AI 使用說明 |
| 原始文件 | [本頁](README.md) |

### 本作業內容

1. **作業總覽**：把 HW1–HW10 整理成這份 `README.md`。
   每個作業都有獨立的章節與完整小節，包含簡介、功能、快速開始、測試結果與限制，
   可以單獨閱讀，不需要先讀其他作業。
2. **PyPI 發佈**：完成 `cafeteria-sim` 的建置、`twine check`、TestPyPI 驗證與正式發佈，
   目前版本為 0.1.1。
3. **AI 使用說明**：在 `cafeteria-sim` 的 README 與 PyPI 專案頁加入給 AI 助手使用的
   「AI 使用說明」，內容包含套件定位、參數單位、建議工作流程、prompt 範例、
   回答時應遵守的規則與驗證方式。

### 成果連結

- PyPI 套件頁：<https://pypi.org/project/cafeteria-sim/>
- HW10 原始碼與完整 AI 說明：[HW10/README.md](../HW10/README.md)
- 作業索引：[homework/README.md](../README.md)

### 備註

- 本文件只整理 HW1–HW10 的內容與連結，各作業的原始碼與完整文件仍保留在各自的資料夾。
- repo 中沒有 HW5 資料夾，因此目錄依實際存在的作業編號排列。

[回目錄](#toc)

---

## 跨作業技術棧總覽

| 領域 | 使用技術 | 對應作業 |
|---|---|---|
| 程式語言 | Python、JavaScript、Rust、SQL、Bash | HW1–HW10 |
| 後端 | Python 標準庫、Flask、Node.js、Axum、Cloudflare Workers | HW2、HW6、HW7、HW9 |
| 前端 | HTML/CSS/JavaScript、Canvas、PWA、Service Worker | HW1、HW2、HW7、HW9 |
| 資料庫 | SQLite、PostgreSQL、Cloudflare D1 | HW2、HW3、HW6、HW7、HW8、HW9 |
| 容器與部署 | Docker、Docker Compose、nginx、Wrangler | HW6、HW9 |
| 測試 | unittest、Playwright、Bash `test.sh` | HW1、HW2、HW3、HW7、HW10 |
| 套件與發佈 | `pyproject.toml`、`build`、`twine`、PyPI | HW10、HW11 |
| 版本控制 | Git、GitHub Flow、Pull Request | 全部作業 |

## 快速連結

| 作業 | 原始文件 | 展示／套件 |
|---|---|---|
| HW1 | [HW1/README.md](../HW1/README.md) | [mycurl 線上展示](https://yi-ning-huang.github.io/_se/homework/HW1/mycurl/) |
| HW2 | [HW2/README.md](../HW2/README.md) | [校務系統展示](https://yi-ning-huang.github.io/_se/homework/HW2/docs/) |
| HW3 | [HW3/README.md](../HW3/README.md) | 本機 `archive/site/index.html` |
| HW4 | [HW4/README.md](../HW4/README.md) | [PR #1](https://github.com/YI-NING-HUANG/se_example/pull/1) |
| HW6 | [HW6/README.md](../HW6/README.md) | 本機 <http://localhost:8080/> |
| HW7 | [HW7/README.md](../HW7/README.md) | 本機 <http://127.0.0.1:8787/> |
| HW8 | [HW8/README.md](../HW8/README.md) | 本機 `archive/site/index.html` |
| HW9 | [HW9/README.md](../HW9/README.md) | [GitHub Pages 單檔版](https://yi-ning-huang.github.io/_se/homework/HW9/) |
| HW10 | [HW10/README.md](../HW10/README.md) | [PyPI](https://pypi.org/project/cafeteria-sim/) |
| HW11 | [本頁](README.md) | — |

## 授權與資料權利

各作業的授權依其資料夾內的 `LICENSE` 或 README 說明為準。
論壇文章、圖片、插件與其他檔案的著作權屬於原作者；
HW3 與 HW8 只協助保存公開內容，不改變原授權，也不應被用來大量再散布他人的作品。
