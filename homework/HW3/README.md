# ForumKeep

ForumKeep 是一套用 Python 標準庫寫成的**公開、唯讀論壇離線保存工具**。
它會沿著站內連結抓取公開頁面，收集文章中的圖片、附件、CSS、字型等素材，
最後產生一個可直接用瀏覽器打開的靜態離線網站，並保留原始 HTML 與素材雜湊。

> 只適用於公開內容。使用前請確認站方規範、robots.txt 與著作權要求。
> 本工具不登入、不發文、不繞過權限，預設也不會下載會員私訊或需要登入的頁面。

## 1. 動機：為什麼要做 ForumKeep？

我長期關注的一些舊論壇，因為主機老化、維護成本、站方生涯規劃等原因陸續決議關站。
這些論壇裡不只有討論，還有大量遊戲製作素材、插件、工具、教學與附件；
一旦關站，這些東西往往來不及備份，就會從網路上消失。

因此我開始思考：有沒有一個工具，可以在不造成站方負擔、不繞過權限的前提下，
把公開的頁面與素材完整保留下來，而且中斷後還能續傳？
最初的構想是做成 VS Code 插件，讓使用者在編輯器裡指定論壇、預覽抓取結果與管理封存。
實際往下做之後，發現核心問題是可續傳的爬取、素材下載與離線建站，
所以目前先把核心做成不依賴編輯器的 Python CLI；VS Code 仍是開發、檢視 HTML/CSS
與測試的主要工具。未來若要做插件，可以直接呼叫這個 CLI 或重用 `forumkeep` 套件。

### 使用價值

- 對自己：把關注的遊戲素材、插件與教學從即將關閉的論壇搬到可長期保存的離線封存。
- 對社群：讓版主、研究者、創作者在關站前用低成本方式保留公開資產。
- 對作品集：展示網路爬蟲、資料庫、檔案系統、靜態網站與測試的整合能力。

### 商業價值

- 老論壇／遊戲工作室的素材盤點、遷移與離線備份案。
- 社群網站關站前的「公開內容保存」顧問與客製化工具。
- 目前先以開源工具與作品集驗證需求，尚未商業化；若需求成立，
  可延伸成付費的託管、驗證與長期保存服務。

## 2. 目前進度與技術

### 目前進度

目前已完成可運作的核心 MVP：

- 可從一個公開論壇首頁開始，沿站內連結抓取頁面。
- 可下載文章中的圖片、附件、CSS、字型等素材，並探索 CSS 依賴。
- 可中斷後續傳，最後產生可離線瀏覽的靜態網站。
- 有 `status`、`verify`、`export` 等維運指令。
- 36 個 unittest 全數通過；`test.sh` 的端到端檢查 `PASS=10 FAIL=0`。
- 附本機範例論壇與展示封存：`tast.sh/artifacts/demo/site/index.html`。

尚未完成或暫不在範圍內：

- VS Code 插件的圖形介面（目前是 Python CLI 核心）。
- 登入、會員、私訊、發文等需要權限的互動功能。
- 純 JavaScript 動態載入的內容。
- WARC 格式輸出與超大規模網站的效能調校。

### 已實作功能

- **禮貌爬取**：預設遵守 `robots.txt`、同一主機限速、可設定重試與逾時。
- **可續傳**：所有佇列、頁面、素材與錯誤都存在 SQLite；中斷後重跑會接續。
- **只讀保存**：不帶登入 cookie，不送出表單，不執行 JavaScript。
- **完整素材**：HTML 頁面、圖片、附件、壓縮檔、文件、CSS、字型、影音。
- **CSS 依賴探索**：下載 CSS 後會繼續找 `url(...)` 與 `@import` 的圖片/字型。
- **SHA-256 命名**：素材以內容雜湊命名，可辨識重複內容；資料庫記錄每個素材的雜湊。
- **離線網站**：重寫站內連結與素材路徑，產生首頁、頁面列表、版面列表、
  討論串列表、素材庫、全文搜尋與 manifest。
- **保留原始資料**：原始 HTML 存在 `raw/pages/`，素材 blob 存在 `blobs/`。
- **驗證與修復**：`verify` 檢查雜湊與檔案；`verify --fix` 把損壞項目重新排隊。
- **匯出**：可把 pages / assets / links 匯出成 JSONL 或 CSV。
- **零第三方依賴**：只需要 Python 3.11+。

### 使用語言、工具與軟體

- 程式語言：Python 3.11+（以 3.12.10 測試），只使用標準庫，沒有第三方套件。
- 測試與自動化：Bash（Git Bash）撰寫 `test.sh`；沒有使用 PowerShell 實作核心。
- 輸出網站：HTML、CSS、JavaScript（離線搜尋索引）。
- 資料庫：SQLite（Python 內建 `sqlite3`），查詢使用 SQL。
- 開發工具：VS Code（編輯、檢視 HTML/CSS、除錯）、Git（版本控制）、瀏覽器（檢查離線網站）。
- 主要標準庫：`urllib.request`、`html.parser`、`sqlite3`、`hashlib`、`re`、
  `json`、`argparse`、`pathlib`、`unittest`、`http.server`。

### 使用的資工相關技術

- 廣度優先搜尋（BFS）與佇列式網路爬蟲。
- URL 正規化、同站範圍判斷、`robots.txt` 解析與禮貌限速。
- HTTP client：重新導向、gzip、重試、逾時、串流下載。
- HTML 解析、`srcset` 處理、CSS `url()` 與 `@import` 重寫。
- 內容定址儲存（content-addressable storage）與 SHA-256 雜湊驗證。
- SQLite 佇列、交易、斷點續傳與錯誤狀態管理。
- 靜態網站生成、離線連結重寫、搜尋索引與 manifest。
- 單元測試、mock HTTP server、fixture 與端到端整合測試。
- 安全與倫理：不登入、不繞過權限、預設遵守 robots.txt，
  離線頁面移除原始 script 與事件屬性。

## 需求

- Python 3.11 以上（本專案以 Python 3.12.10 測試）
- 不需要資料庫伺服器、瀏覽器自動化或任何 pip 套件

## 快速開始

### 安裝（可選）

直接從專案根目錄執行也可以；若想使用 `forumkeep` 指令，再安裝：

```bash
python -m pip install -e .
forumkeep --version
```

不安裝時，所有指令都可用 `python -m forumkeep`：

```bash
python -m forumkeep --version
python -m forumkeep --help
```

### 保存一個公開論壇

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

# 6. 打開
# archive/site/index.html
```

也可以一次跑完：

```bash
python -m forumkeep run \
  --url https://example.com/forum/ \
  --out archive \
  --delay 1.5 \
  --max-pages 500
```

### 常用選項

| 選項 | 說明 |
|------|------|
| `--out DIR` | 封存資料夾，預設 `forum-archive` |
| `--delay SEC` | 同一主機請求間隔，預設 `1.0` 秒 |
| `--retries N` | 失敗重試次數，預設 `2` |
| `--timeout SEC` | 單一請求逾時，預設 `30` 秒 |
| `--robots respect\|warn\|ignore` | robots.txt 模式，預設 `respect` |
| `--url URL` | 起始網址，可重複 |
| `--allow-host HOST` | 額外允許的網域，可用 `*.example.com` |
| `--path-prefix PATH` | 只爬取指定路徑前綴，可重複 |
| `--include GLOB` / `--exclude GLOB` | 自訂納入/排除規則 |
| `--no-default-excludes` | 停用登入、搜尋、管理、回覆等預設排除 |
| `--external-assets none\|same-host\|all` | 外部素材範圍，預設 `same-host` |
| `--max-pages N` | 本次最多抓幾頁 |
| `--max-depth N` | 最大連結深度 |
| `--page-mb MB` / `--asset-mb MB` | 單頁 / 單素材大小上限 |
| `--retry-errors` | 重試先前失敗或 blocked 的項目 |
| `--force` | 重新抓取已完成頁面 |
| `--kind LIST` | 只下載指定素材類型，例如 `image,attachment` |
| `--host HOST` | 只下載指定主機的素材 |
| `--limit N` | 本次最多處理幾個素材 |
| `--no-css-deps` | 不從 CSS 探索字型與圖片 |
| `--keep-scripts` | 保留原始 JavaScript（預設移除，不建議） |
| `--no-banner` | 不插入 ForumKeep 離線橫幅 |
| `-v` / `-q` | 詳細進度 / 只顯示錯誤 |

`status`、`verify` 支援 `--json`；`verify` 支援 `--fix`；
`export` 支援 `--format jsonl|csv` 與 `--what all|pages|assets|links`。

## 本機範例

專案附一個可重現的小型論壇：`examples/mini_forum/`。

```bash
# 另開一個終端機
python -m http.server 8765 --directory examples/mini_forum

# 回到專案根目錄
python -m forumkeep run \
  --url http://127.0.0.1:8765/ \
  --out demo \
  --delay 0 \
  --retries 1
```

完成後打開 `demo/site/index.html`。
範例的 `/private/secret.html` 被 `robots.txt` 阻擋，會保留為原始絕對連結，
不會被封存；這可用來確認 robots 與離線重寫行為。

執行測試也會自動產生一份展示封存：

```bash
bash test.sh
# 展示：tast.sh/artifacts/demo/site/index.html
```

## 輸出結構

```text
archive/
├── forumkeep.sqlite3          # 佇列、頁面、素材、連結、錯誤、設定
├── README.txt                 # 封存說明
├── raw/
│   └── pages/                 # 原始 HTML
├── blobs/
│   └── ab/                    # SHA-256 命名的素材 blob
├── site/
│   ├── index.html             # 離線首頁
│   ├── pages.html             # 所有頁面
│   ├── forums.html            # 版面
│   ├── threads.html           # 討論串
│   ├── assets.html            # 素材庫
│   ├── search.html            # 全文搜尋
│   ├── search-index.js
│   ├── style.css
│   ├── manifest.json
│   ├── pages/<host>/          # 離線頁面
│   └── assets/<sha-prefix>/   # 離線素材
└── exports/                   # export 指令的輸出（若有執行）
```

## 測試

```bash
bash test.sh
```

測試腳本會：

1. `compileall` 檢查 `forumkeep/` 與 `tests/`。
2. 執行 36 個 unittest（HTML、robots、policy、store、下載、爬取、建站）。
3. 檢查 CLI `--version` / `--help`。
4. 啟動本機 `127.0.0.1` 的 `examples/mini_forum`，實際跑
   `run` → `status` → `verify`，並檢查頁面/素材數量、robots 阻擋、
   離線首頁、搜尋頁、素材庫、manifest、未封存連結與 blob 完整性。

目前結果：

```text
Ran 36 tests ... OK
結果: PASS=10 FAIL=0
ALL CHECKS PASSED
```

- 測試報告：`tast.sh/test-report.txt`
- 測試資料夾說明：`tast.sh/README.md`
- 端到端展示：`tast.sh/artifacts/demo/site/index.html`

測試只連線到本機隨機 port，不需要外部網路。

## 設計重點

### 1. 政策與範圍

`CrawlPolicy` 決定哪些 URL 可以抓：

- 只允許種子主機與 `--allow-host` 指定的主機。
- 可用 `--path-prefix` 限定路徑。
- 預設排除登入、註冊、搜尋、管理、回覆、編輯、刪除等動作。
- 頁面與素材分開判斷，避免把下載連結當成頁面。
- 外部素材預設只允許與種子同主機；要抓 CDN 圖片需 `--external-assets all`。

### 2. 爬取與續傳

`crawl` 使用 SQLite 佇列做廣度優先搜尋：

- `queue` 記錄頁面待抓、完成、錯誤、blocked、skipped。
- `pages` 記錄原始 HTML 路徑、內容類型、編碼、雜湊、標題。
- `links` 記錄來源、目標、錨文字與是否站內。
- `aliases` 記錄重新導向後的最終網址。
- 每次啟動會把上次中斷的 `working` 佇列改回 `pending`。
- `--retry-errors` 可重試錯誤與 robots blocked 的項目。

### 3. 素材下載

`download` 只處理 `assets` 表中 `pending` 的項目：

- 串流寫入暫存檔，邊下載邊計算 SHA-256 與大小。
- 完成後以雜湊命名存入 `blobs/`；相同內容且相同副檔名會共用 blob。
- 支援 `Content-Disposition` 檔名、重新導向、gzip。
- CSS 下載後會探索 `url(...)` 與 `@import`，把依賴排入佇列。
- 單一素材有大小上限，預設 200 MB。
- 失敗會記錄錯誤與 HTTP 狀態，可用 `--retry-errors` 重試。

### 4. 離線建站

`build` 會：

- 把每個已抓取頁面重寫成 `site/pages/<host>/<hash>.html`。
- 把站內連結改成本地相對路徑；未封存的連結保留原始絕對 URL。
- 把已下載素材改成本地 `site/assets/...` 路徑。
- 改寫 CSS 內的 `url(...)` 與 `@import`。
- 移除原始頁面的 `<script>`（可用 `--keep-scripts` 保留）與 CSP/integrity 屬性。
- 插入離線橫幅與搜尋連結（可用 `--no-banner` 停用）。
- 產生首頁、頁面/版面/討論串列表、素材庫、搜尋索引與 manifest。

### 5. 驗證

`verify` 會重新計算：

- 每個頁面原始 HTML 的 SHA-256。
- 每個已完成素材 blob 的 SHA-256 與大小。
- 缺少的檔案與資料庫紀錄不一致。

`verify --fix` 會把損壞頁面/素材重新排入佇列；再跑 `crawl`/`download`
即可修復。素材修復後會覆蓋損壞 blob，不會誤用舊檔。

## 限制

- 不執行 JavaScript，因此純前端動態載入的內容不會被發現。
- 不處理登入、會員、私訊、投票、發文等互動功能。
- 不繞過付費牆、權限控制或 robots.txt；`--robots ignore` 僅供你確認
  自己有權存取的站台，不建議使用。
- CSS 解析是輕量實作，不保證涵蓋所有 CSS 語法。
- 預設只抓與種子同主機的素材；跨網域 CDN 需明確設定。
- 不是 WARC 工具；原始 HTML 與素材分開保存，離線網站是另外產生的。
- 檔名會做 Windows 安全字元處理，極少數原始檔名可能被調整。

## 專案結構

```text
HW3/
├── forumkeep/
│   ├── __init__.py
│   ├── __main__.py
│   ├── build.py          # 離線網站、HTML/CSS 重寫、搜尋、manifest
│   ├── cli.py            # 命令列入口與 pipeline
│   ├── crawl.py          # BFS 爬取、頁面解析、素材探索
│   ├── download.py       # 串流下載、CSS 依賴、blob 命名
│   ├── htmlx.py          # HTML parser、srcset、CSS url 解析
│   ├── net.py            # HTTP client、robots、限速、重試、gzip
│   ├── policy.py         # 網域/路徑/排除/素材政策
│   ├── store.py          # SQLite schema 與查詢
│   ├── util.py           # URL、檔名、編碼、雜湊、大小工具
│   └── verify.py         # 雜湊與檔案驗證
├── tests/                # 36 個 unittest + mock forum/server
├── examples/mini_forum/  # 可重現的本機範例論壇
├── tast.sh/              # 測試入口、報告、端到端展示產物
├── test.sh               # 根目錄一鍵入口（轉呼叫 tast.sh/test.sh）
├── pyproject.toml
├── README.md
└── LICENSE
```

## 授權

MIT，詳見 `LICENSE`。
