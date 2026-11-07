# xfrescue

`xfrescue` 是一套用 Python 標準庫寫成的 XenForo 論壇備份工具，目標是保存 **RPG Maker Web 論壇**（`forums.rpgmakerweb.com`）在唯讀與關站前的公開內容，尤其是插件、素材與其他可下載檔案。

它會把討論串、文章、作者、時間、原始 HTML、附件與外部檔案抓下來，最後產生一份可離線瀏覽的靜態網站。所有進度都存在 SQLite，中斷後重跑同一道命令即可續傳。

## 價值主張（對應作業需求）

**使用價值（已成立）**

- **我自己就是使用者**：RPG Maker Web 論壇已於 2026-06-18 轉為唯讀，並將於 2026-12-11 關閉；我需要把插件、素材、教學與公告備份到本機，關站後仍能查閱。
- **需求真實且公開**：關站消息在 RPG Maker 社群引發大量備份討論。現有方案各有缺口：`rpgmakerchat` 是線上 archive、`dragonrefuge` 是現成唯讀 app、Internet Archive 偏 WARC；本工具補上「可續傳、以檔案為中心、可自行驗證」的位置。
- **離線真的可用**：產生的靜態網站不依賴原站，支援討論串瀏覽、附件清單與**全部文章全文搜尋**（`site/search.json` 內含 threads 與 posts，搜尋結果直接跳到 `#post-ID`）。

**商業價值（可延伸）**

- **可接案**：任何 XenForo 論壇在遷移、關站或改版前，都需要選擇性備份、附件盤點、離線交付與 hash 驗證。同一套流程換 forum ID、preset、站台設定即可重用。
- **可產品化**：以「保存專案」計價（一次性掃站 + 客製靜態站 + 驗證報告），或提供定期快照、異地備份訂閱；也可作為論壇搬遷前的資料盤點工具。
- **成本結構清楚**：單機執行、零第三方 Python 依賴、SQLite 續傳，不需要雲端基礎設施，適合個人或小型工作室接案。

## 先說清楚：這個討論串不是插件串

指定目標：

```text
https://forums.rpgmakerweb.com/threads/welcome-to-rpg-maker-guild.183984/
```

這是 **「Welcome to RPG MAKER GUILD」公告串**，不是插件發布串。實際內容是：

- 273 篇文章、14 頁
- 26 個 asset 參照
- 其中 18 個是論壇附件，幾乎都是 PNG/JPG 圖片
- 1 個是 `link_only` 的外部頁面（itch.io）
- 沒有插件 zip

因此本專案已把這個公告串完整備份成範例（`demo/`），但如果你要的是「所有已發布的插件檔案」，必須再 crawl 插件與資源 forum。工具已內建 preset，指令在下面。

## 為什麼不直接爬官方論壇

官方論壇的 `robots.txt` 目前是：

```text
User-agent: *
Disallow: /
Crawl-delay: 10
```

只允許 Googlebot。工具預設 `--robots respect`，會拒絕下載被 disallow 的 URL。這個限制沒有被繞過。

另外，論壇將於 **2026-12-11（JST）** 關閉，2026-06-18 起唯讀。時間有限，但請不要用無限制併發去撞站。

本工具採用混合來源：

1. **社群 archive API**（`https://rpgmakerchat.com/api/...`）取得完整的文章文字、作者、時間與 asset URL。該站 robots 允許一般爬蟲。
2. **官方論壇 live HTML**（可選）取得原始頁面、附件與 archive API 沒收錄的內容。
3. **下載器**負責附件、圖片、壓縮檔、GitHub raw 等檔案，含 rate limit、重試、SHA-256 去重與續傳。
4. **靜態網站產生器**把資料變成離線 HTML。

`--robots warn` 只應用在你有權限進行的保存工作。專案不提供登入繞過、付費牆繞過或私訊存取。

## 已完成的範例

`demo/` 是目標公告串的實際備份：

- 273 posts，全部進入離線全文搜尋索引
- 18/26 assets 已下載（1.8 MB）
- 7 個外部圖片仍為 pending
- 1 個 link-only 外部頁面
- 已產生 `demo/site/index.html` 與討論串頁面

`demo_live/` 是 live HTML parser 的兩頁測試樣本，用來驗證官方論壇版型解析。兩者都被 `.gitignore` 排除，不會進 git。

## 實測：社群 → 資源（2026-11-07）

以 forum `28`（General Resources）實測：

```bash
python -m xfrescue --out test_resources discover --forum 28 --with-posts --max-threads 3
python -m xfrescue --out test_resources --robots warn download --kind attachment --limit 2
python -m xfrescue --out test_resources download --kind image --host live.staticflickr.com --limit 2
python -m xfrescue --out test_resources build
```

結果：

- 3 個討論串、817 篇文章、260 個 asset 參照。
- 成功下載 **2 個論壇附件**（GIF/PNG）與 **2 個 Flickr 圖片**，SHA-256 驗證 4/4 通過。
- 離線頁面已把圖片 `src` 改寫成本機 `assets/...` 路徑，關站後仍可顯示。
- 官方論壇附件受 `robots.txt` 限制：預設 `respect` 會回報 `blocked` 並以 exit 3 結束，不會把資產誤記為損壞；`warn` 模式僅供有保存權限時使用。
- 實測也發現並修正 MediaFire 下載頁（網址結尾看似 `.zip`，實際回傳 HTML）被誤判為可直接下載的問題；現在一律標為 link-only，只有 CDN 直連檔才下載。

`test_resources/` 是本次實測產物（含已下載檔案），已列入 `.gitignore`。

## 安裝

需求：Python 3.11 以上。沒有第三方 Python 依賴。

```bash
python -m xfrescue --help
```

或安裝成命令：

```bash
pip install -e .
xfrescue --help
```

### Docker

```bash
docker build -t xfrescue .
docker run --rm -v "%cd%/archive:/data" xfrescue --out /data/archive init
```

Windows PowerShell 也可以用：

```powershell
docker run --rm -v "${PWD}/archive:/data" xfrescue --out /data/archive init
```

Git Bash 會把容器內的 `/data` 轉成 Windows 路徑；若使用 Git Bash，請加 `MSYS_NO_PATHCONV=1`：

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "C:/path/to/archive:/data" xfrescue --out /data/archive init
```

或使用 compose：

```bash
docker compose run --rm xfrescue --out /data/archive init
```

## 快速開始：備份指定討論串

```bash
python -m xfrescue --out archive init
python -m xfrescue --out archive discover --thread 183984
python -m xfrescue --out archive download --kind attachment
python -m xfrescue --out archive build
```

開啟：

```bash
start archive\site\index.html
```

如果官方論壇的附件需要 live 下載，而 robots 檢查會擋下：

```bash
python -m xfrescue --out archive --robots warn download --kind attachment
```

再次提醒：`warn` 只在你確認有保存權限時使用。工具會在 stderr 印出每一個被 disallow 的 URL。

## 備份插件與資源 forum

只抓論壇列表與文章，不下載檔案：

```bash
python -m xfrescue --out archive discover --preset plugins --with-posts
```

下載所有已記錄的檔案：

```bash
python -m xfrescue --out archive --robots warn download
```

把插件、資源、公告 forum 都納入：

```bash
python -m xfrescue --out archive discover --preset assets --with-posts
python -m xfrescue --out archive --robots warn download
python -m xfrescue --out archive build
```

全站（很大，會跑很久）：

```bash
python -m xfrescue --out archive discover --all-forums --with-posts
python -m xfrescue --out archive --robots warn download
```

全站約 151,936 個討論串、百萬級文章。請預期數天以上，並用預設的 `--delay 1.0` 或更高。中斷是安全的；重跑同一道命令會從 SQLite 續傳。

### 指定 forum 或 thread

```bash
python -m xfrescue --out archive discover --forum 199 --with-posts
python -m xfrescue --out archive discover --thread https://forums.rpgmakerweb.com/threads/183984/
```

`--thread` 與 `--forum` 都可重複指定。`--max-threads`、`--max-pages` 可限制單次工作量。

### 使用 live HTML

```bash
python -m xfrescue --out archive --robots warn discover \
  --source live \
  --thread https://forums.rpgmakerweb.com/threads/welcome-to-rpg-maker-guild.183984/ \
  --max-pages 3
```

live 模式會保存原始 HTML 到 `raw/live/`，並解析文章與 asset。這是 best-effort：XenForo 版型改動可能讓 parser 失效，請以測試與 `verify` 檢查。

## 指令

| 指令 | 用途 |
| --- | --- |
| `init` | 建立 archive 目錄與 SQLite |
| `list-forums` | 列出已知 forum；`--refresh` 重新抓取 |
| `discover` | 探索 thread/forum、文章與 asset URL |
| `download` | 下載 pending asset；可限 kind/host/數量 |
| `build` | 產生離線靜態網站 |
| `status` | 顯示 counts、bytes、錯誤 |
| `verify` | 檢查檔案 hash；`--fix` 把壞檔重設為 pending |
| `export` | 匯出 forums/threads/posts/assets 為 JSONL 或 CSV |

共同參數可放在子命令前或後：

```text
--out DIR           archive 目錄（預設 ./archive）
--delay SECONDS     同一 host 的請求間隔（預設 1.0）
--timeout SECONDS   單一請求 timeout
--retries N         重試次數
--user-agent STRING 自訂 UA
--robots MODE       respect / warn / ignore（預設 respect）
-v, --verbose       詳細輸出
--archive-base URL  社群 archive API base
```

常用 `discover` 參數：

```text
--source archive|live
--thread ID_OR_URL     可重複
--forum ID_OR_URL      可重複
--preset announcements|plugins|resources|assets|everything
--all-forums
--with-posts
--max-threads N
--max-pages N
--force                live 模式重抓
--no-raw               不存原始 JSON/HTML
```

常用 `download` 參數：

```text
--kind attachment,image,archive,code,document,audio,video,page_asset
--limit N
--host HOST
--max-mb N
--dry-run
--retry-errors
```

## 輸出結構

```text
archive/
  xfrescue.sqlite3          # 進度、metadata、asset 狀態
  assets/                   # 實際檔案（依 host 分目錄）
  raw/
    archive/                # 社群 API 原始 JSON
    live/                   # 官方論壇原始 HTML
  site/
    index.html
    threads/183984/index.html
    forums/199/index.html
    assets.html
    assets.csv
    search.json
  exports/
```

同一份檔案內容只會存一次（SHA-256 去重），DB 內不同 URL 可指向同一個 local path。

## 設計與安全邊界

- 只處理公開頁面；不登入、不繞過付費牆、不存取私訊。
- 預設尊重 `robots.txt` 與 `Crawl-delay`；`--robots ignore` 只保留給明確有權限的情況。
- 預設 1 秒/同一 host，且遇到 `429`/`503` 會退避。
- 下載有大小上限（預設 200 MB/檔），避免誤抓巨大檔案。
- 只保存檔案與靜態 HTML，不執行 JavaScript，也不保存完整原始 CSS/JS。
- 外部檔案若 403/404/404，會記錄為 error，之後可用 `--retry-errors` 重試。
- 需要登入才看得到的附件不會被下載；這是刻意設計。

## 驗證

```bash
python -m unittest discover -s tests -v
```

目前 27 個測試，涵蓋分類、HTML parser、archive API、下載、robots 阻擋、SQLite、builder 與全文搜尋索引，全部使用本機 mock server，不需要網路。

驗證已下載檔案：

```bash
python -m xfrescue --out archive verify
python -m xfrescue --out archive verify --fix
```

## 已知限制

- Live HTML parser 只針對目前 XenForo 版型，站方改版可能需要更新 selector。
- JS-only 嵌入（例如部分 itch.io/YouTube 預覽）只保留連結，不保證可離線播放。
- 不是 WARC；這是「可閱讀的靜態備份」，不是像素級完整 replay。
- 附件若需要登入，工具不會嘗試取得。
- 全站 crawl 的規模很大，請先從 `--preset plugins` 或單一 forum 開始。

## 與 HW3（ForumKeep）的差異

HW3 的定位是「任意公開論壇的通用 BFS 爬蟲」；HW8 則是「XenForo／RPG Maker Web 關站保存」的專用資料管線。以下只列不同與強化處，兩者相同的標準庫、SQLite 續傳、robots、SHA-256 去重與離線網站不再重述。

| 面向 | HW3 ForumKeep | HW8 xfrescue |
| --- | --- | --- |
| 入口 | 任意 seed URL，沿站內連結 BFS | forum/thread ID、preset（plugins/resources/assets/everything） |
| 主要來源 | live HTML 爬取 | 社群 archive JSON API；live XenForo HTML 可選 |
| 資料單位 | page / queue / link / alias | forum / thread / post（作者、樓層、時間、HTML、純文字、URL） |
| 資源判定 | 通用副檔名＋CSS 依賴 | XenForo 附件優先、GitHub blob→raw、檔案主機頁 vs CDN 直連 |
| 離線輸出 | 重寫原始頁面 | 重建討論串分頁（50 篇/頁）、forum 頁、素材 CSV |
| 搜尋 | 頁面級 | thread＋post 級，直接跳到 `#post-ID` |
| 交付 | mini_forum＋test.sh E2E | 真實 273 篇 demo＋forum 28 資源實測＋Docker |

### 1. 來源架構：從 live 爬取改成 archive API 優先

HW3 只能從 live HTML 開始 BFS，因此遇到官方論壇 `robots.txt` 全面 `Disallow: /` 時會直接 blocked，無法取得內容。HW8 增加 `rpgmakerchat.com` 的社群 JSON archive API 作為主要來源：可取得完整文章文字、作者、時間與 asset URL，且該站允許一般爬蟲；官方論壇的 live HTML 則降為可選來源，用於需要原始頁面或 archive API 未收錄內容時。

這是兩個專案最根本的差異：HW3 是「站方允許才爬得到」；HW8 是「官方不允許時，改用已存在的社群 archive，並保留禮貌性的 live 模式」。

### 2. 資料模型：page 級 → post 級

HW8 新增 `forums/threads/posts` 三層結構，每篇文章獨立記錄 `post_index`、`posted_at`、`content_html`、`content_text`、原始 URL 與所屬 thread。這讓 HW8 可以：

- 依樓層重建討論串分頁，而不是保存一整頁混在一起的 HTML。
- 在離線網站產生 `#post-ID` 錨點，搜尋結果可直接跳到某一篇回覆。
- 只更新缺少頁數的 thread，不必整串重抓。
- 輸出 assets 與 post 的關聯，顯示「這篇回覆附了哪些檔案」。

HW3 的 page/queue 模型仍適合任意網站，但無法表達「第幾樓、誰在什麼時候發文」這種論壇語意；HW8 是針對這個語意重新設計 schema。

### 3. 資源分類與下載：XenForo 專用強化

- **附件優先**：`/attachments/`、`/data/attachments/` 直接標為 attachment（priority 0），論壇頁面、頭像、CSS/JS 等 page asset 分開處理，避免把討論串頁面誤當檔案。
- **分享連結正規化**：GitHub `blob` 自動改寫成 `raw`；Google Drive、Dropbox 分享連結會正規化，但無法確認是直連檔者仍標為 link-only。
- **下載頁 vs 直連檔**：HW8 會區分「檔案主機頁」與「CDN 直連檔」。例如 MediaFire 的 `/download/....zip` 雖然網址結尾是 `.zip`，實際回傳 HTML；本版已修正為 link-only，不會把 HTML 存成假 ZIP。這是本次實測社群資源區時發現並補上的。
- **blocked 與 error 分離**：下載遇到 robots 阻擋時保留 pending、回報 blocked 數量；若全部被擋，CLI 以 exit 3 結束，不會把資產誤記成損壞。

HW3 的 CSS `url(...)`／`@import` 依賴探索並沒有搬進 HW8；HW8 的目標是文章中的附件與外部檔案，不是完整前端資產鏡像。

### 4. 離線網站與搜尋：重建討論串，而不是重寫原頁

HW3 把抓到的原始頁面直接重寫，優點是保留頁面原貌，搜尋以「頁」為單位。HW8 則從結構化 posts 重建：

- 每個討論串依 50 篇一頁產生頁碼導覽。
- 每篇回覆下方列出該文章的下載檔案。
- 另外產生 forum 列表、素材表 `assets.html`／`assets.csv` 與 manifest。
- `search.json` 同時索引 **thread 與 post**；thread 結果導向討論串，post 結果導向 `#post-ID`。這是 HW8 相對 HW3 最主要的輸出強化。

### 5. CLI、部署與交付差異

- HW8 新增 `list-forums`、`discover --source archive|live`、`--preset`、`--max-threads/--max-pages`、`--no-raw`、`--archive-base` 等站點導向參數。
- HW8 的 `export` 支援 forums/threads/posts/assets；HW3 是 pages/assets/links。
- HW8 內建 `Dockerfile` 與 `docker-compose.yml`；HW3 沒有。
- HW8 附真實 273 篇文章的 `demo/`，以及 forum 28（General Resources）的 `test_resources/` 實測；HW3 附可重現的 `mini_forum` 與 `test.sh` E2E。

### 6. HW8 刻意未重複的 HW3 能力

以下不是退化，而是兩個工具的目標不同：

- HW3 的通用 BFS、`--allow-host`、`--path-prefix`、`--include/--exclude` 政策 DSL：HW8 不需要，因為入口已改成 forum/thread/preset。
- HW3 的 CSS 依賴圖與原頁面 HTML 驗證：HW8 聚焦在 post 與附件，`verify` 只驗證已下載檔案。
- HW3 的 `test.sh` 端到端本機論壇測試：HW8 改用 unittest＋mock server，並以真實 archive 做驗收。

## 與現有保存方案的關係

- `https://rpgmakerchat.com`：已有的完整社群 archive 與 JSON API，本工具用它取得文章內容。
- `https://dragonrefuge.itch.io/rmw-archive`：現成的 Windows 離線 archive app，適合只想下載現成備份的人。
- Internet Archive / Archive Team：適合 WARC 與全站鏡像。
- 新官方論壇：`https://guild.rpgmakerofficial.com`。

`xfrescue` 的定位是：**可續傳、以檔案為中心、可自行驗證的本機保存工具**，不是要取代上述方案。

## 專案結構

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
tests/            # unittest + mock server
Dockerfile
docker-compose.yml
```

## 授權與內容權利

程式碼以 MIT 釋出。論壇文章、圖片、插件與其他檔案的著作權屬於原作者；本工具只協助保存，不改變授權，也不應被用來大量再散布別人的作品。
