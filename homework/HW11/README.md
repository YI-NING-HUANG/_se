# 現代軟體工程作業總覽（HW1–HW11）

本 repo 是「現代軟體工程」課程的作業與專案彙整。HW1–HW10 分別對應不同的軟體工程主題，
HW11 則是把前九個作業整理成這份索引，並完成套件發佈與 AI 使用說明。

點選下方目錄即可跳到對應作業的完整內容。

## 目錄（依週次）

| 週次 | 作業 | 主題 | 內容 |
|---|---|---|---|
| 1 | HW1 | mycurl：類 curl 的 CLI | [開啟](../HW1/README.md) |
| 2 | HW2 | 校務系統 Web 應用（三個版本） | [開啟](../HW2/README.md) |
| 3 | HW3 | ForumKeep 公開論壇離線保存 | [開啟](../HW3/README.md) |
| 4 | HW4 | Git flow / GitHub flow 與 PR | [開啟](../HW4/README.md) |
| 6 | HW6 | Docker Compose 微服務系統 | [開啟](../HW6/README.md) |
| 7 | HW7 | DINO RUN 離線小恐龍 PWA | [開啟](../HW7/README.md) |
| 8 | HW8 | xfrescue XenForo 論壇備份 | [開啟](../HW8/README.md) |
| 9 | HW9 | DINO RUN on Cloudflare + D1 | [開啟](../HW9/README.md) |
| 10 | HW10 | cafeteria-sim 排隊模擬套件 | [開啟](../HW10/README.md) |
| 11 | HW11 | 作業總覽、PyPI 發佈與 AI 使用說明 | [本頁](README.md) |

> 註：repo 中沒有 HW5 資料夾，以下依實際存在的作業編號整理。

## 依主題分類

| 分類 | 作業 | 內容簡介 |
|---|---|---|
| A. CLI 與網路工具 | [HW1](../HW1/README.md) | 只用 Python 標準庫實作 curl，含 mycurl2 網頁介面 |
| B. Web 應用與資料庫 | [HW2](../HW2/README.md)、[HW7](../HW7/README.md) | 校務系統（SQLite）與 DINO RUN 遊戲（Canvas + SQLite 排行榜） |
| C. 爬蟲與資料保存 | [HW3](../HW3/README.md)、[HW8](../HW8/README.md) | 公開論壇的禮貌爬取、續傳、離線網站與全文搜尋 |
| D. 系統、容器與雲端 | [HW6](../HW6/README.md)、[HW9](../HW9/README.md) | Docker Compose 微服務，以及 Cloudflare Workers + D1 部署 |
| E. Git 協作流程 | [HW4](../HW4/README.md) | fork、功能分支、merge 與 Pull Request |
| F. 套件工程與發佈 | [HW10](../HW10/README.md)、[HW11](README.md) | Python 套件打包、PyPI 發佈、AI 使用說明 |

## 作業摘要

### HW1：mycurl — 類 curl 的 CLI

**分類**：A. CLI 與網路工具  
**重點**：只用 Python 標準庫（`urllib`、`ssl`、`argparse`）實作 HTTP 客戶端，
支援 GET/POST、標頭、JSON、存檔、重新導向、Basic 認證、SSL 略過、結束碼對齊 curl。
`mycurl2.py` 是超集，增加 `--html-out`、`--serve`、`--demo-out`。

**技術**：Python 3.8+ 標準庫、unittest、Bash 測試腳本  
**成果**：`test.sh` 為 PASS=14 FAIL=0，含 13 個單元測試與實機請求。

[完整內容](../HW1/README.md) ｜ [線上展示](https://yi-ning-huang.github.io/_se/homework/HW1/mycurl/)

### HW2：校務系統 Web 應用

**分類**：B. Web 應用與資料庫  
**重點**：以 Python 標準庫 + SQLite 實作選課系統，分成三個版本：
v1.0 選課核心（登入、查詢、加退選、擋修、課表）、
v1.1 加上成績與 GPA、v1.2 加上老師登分與管理員開課。
每一版都有獨立測試與前一版回歸測試。

**技術**：Python 標準庫、`sqlite3`、HTML/CSS/JS、Bash  
**成果**：三個版本皆 PASS=13 FAIL=0。

[完整內容](../HW2/README.md) ｜ [線上展示](https://yi-ning-huang.github.io/_se/homework/HW2/docs/)

### HW3：ForumKeep 公開論壇離線保存

**分類**：C. 爬蟲與資料保存  
**重點**：從公開論壇首頁沿站內連結爬取頁面，下載圖片、附件、CSS、字型，
以 SHA-256 內容雜湊命名，並產生可離線瀏覽的靜態網站。
支援中斷續傳、`robots.txt`、限速、驗證與匯出。

**技術**：Python 3.11+ 標準庫、SQLite、BFS 爬蟲、HTML 解析、靜態網站生成  
**成果**：36 個 unittest 通過，端到端 `test.sh` 為 PASS=10 FAIL=0。

[完整內容](../HW3/README.md)

### HW4：Git flow / GitHub flow 與 Pull Request

**分類**：E. Git 協作流程  
**重點**：示範 Forking Workflow：fork 母專案、建立 `developGitBranch`、
在分支開發並 merge 回 fork 的 `main`，最後對母專案發 Pull Request。
完整記錄 branch、merge、reflog 與 PR 流程。

**技術**：Git、GitHub、Markdown  
**成果**：PR #1 已建立，流程與指令都有紀錄。

[完整內容](../HW4/README.md)

### HW6：Docker Compose 微服務系統

**分類**：D. 系統、容器與雲端  
**重點**：以 Docker Compose 建立五個服務：nginx 反向代理、
Node.js API、Python Flask 運算服務、Rust Axum 服務、PostgreSQL 16。
只有 nginx 對外開放 8080，其餘服務走 Compose 內部網路。
Rust 使用 multi-stage build，資料庫有 healthcheck 與 named volume。

**技術**：Docker、Docker Compose、nginx、Node.js、Python、Rust、PostgreSQL  
**成果**：可用 Web 介面測試服務狀態、Notes CRUD 與各後端端點。

[完整內容](../HW6/README.md)

### HW7：DINO RUN 離線小恐龍 PWA

**分類**：B. Web 應用與資料庫  
**重點**：以 Canvas 實作無限跑酷遊戲，包含仙人掌、翼龍、晝夜變化、
Web Audio 音效、手機觸控與 PWA 離線遊玩。
後端使用 Python 標準庫 `ThreadingHTTPServer` + SQLite 提供排行榜 API。

**技術**：HTML/CSS/JavaScript、Canvas、Service Worker、Python、SQLite、Playwright  
**成果**：18 個 server 單元測試、19 個 API 系統測試、6 個 Playwright E2E 測試。

[完整內容](../HW7/README.md)

### HW8：xfrescue XenForo 論壇備份

**分類**：C. 爬蟲與資料保存  
**重點**：針對 XenForo 論壇的公開內容備份工具，抓取討論串、文章、作者、
原始 HTML、附件與外部檔案，最後產生離線靜態網站與全文搜尋索引。
所有進度存在 SQLite，中斷後可續傳；素材以 SHA-256 去重與驗證。

**技術**：Python 3.11+ 標準庫、SQLite、HTML 解析、Docker  
**成果**：已備份指定公告串（273 篇文章）並產生可離線瀏覽的 `demo/site`。

[完整內容](../HW8/README.md)

### HW9：DINO RUN on Cloudflare

**分類**：D. 系統、容器與雲端  
**重點**：把 HW7 的小恐龍搬上 Cloudflare：前端由 Workers Static Assets 託管，
排行榜 API 改寫成 Cloudflare Worker，資料存進 D1（SQLite 相容）。
保留 HW7 的 PWA 與 API 格式，並增加 CORS、單檔 HTML 分享版。

**技術**：Cloudflare Workers、Workers Static Assets、Cloudflare D1、Wrangler、JavaScript  
**成果**：`/api/health`、`/api/scores`、`/api/stats` 可在雲端執行，
另提供 GitHub Pages 單檔版。

[完整內容](../HW9/README.md) ｜ [GitHub Pages 單檔版](https://yi-ning-huang.github.io/_se/homework/HW9/)

### HW10：cafeteria-sim 排隊模擬套件

**分類**：F. 套件工程與發佈  
**重點**：以 SimPy 建立的學餐排隊離散事件模擬套件，支援多窗口、
共用／獨立取餐動線、balk、renege、暖機與多種服務時間分布。
CLI 提供 `run`、`compare`、`optimize`、`demo`，可在等候目標下找最低成本人力配置。

**技術**：Python 3.10+、SimPy、argparse、unittest、setuptools、PyPI  
**成果**：35 個 unittest 通過、`twine check` 通過，已發佈至 PyPI 0.1.1。

[完整內容](../HW10/README.md) ｜ [PyPI 套件頁](https://pypi.org/project/cafeteria-sim/)

### HW11：作業總覽、PyPI 發佈與 AI 使用說明

**分類**：F. 套件工程與發佈  
**重點**：將 HW1–HW10 的內容分類整理成這份總覽；
完成 `cafeteria-sim` 的 PyPI 發佈，並在套件頁加入給 AI 助手使用的
「AI 使用說明」（參數單位、工作流程、prompt 範例、驗證方式）。

**技術**：Markdown、Git、PyPI、twine  
**成果**：HW11 目錄可連到每個作業；PyPI 0.1.1 頁面已包含 AI 使用說明。

[PyPI 套件頁](https://pypi.org/project/cafeteria-sim/) ｜ [HW10 原始碼與 AI 說明](../HW10/README.md)

## 技術棧總覽

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

## 快速開始

想直接看某個作業，從上面的[目錄](#目錄依週次)點進去即可。
每個作業資料夾都有自己的 `README.md`；多數作業也附有 `test.sh` 或測試指令。

- 回到 [homework 索引](../README.md)
- 回到 [repo 首頁](../README.md)
