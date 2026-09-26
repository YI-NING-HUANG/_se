# HW1：做一個類似 curl 的程式（mycurl / mycurl2）

> 線上展示頁（排版版）：https://yi-ning-huang.github.io/_se/homework/HW1/mycurl/
> 本機雙擊即看：`mycurl/index.html`

## 1 · 專案簡介（動機與介紹）

**mycurl** 是一個「最小可用版的 curl」：用**純 Python 標準函式庫**寫成的命令列 HTTP 客戶端。
你在終端機給它 URL 和選項，它就發出 HTTP 請求，把伺服器回傳的內容印出來或存成檔案。

**為什麼做這個？** curl 是每個工程師都會用到的網路工具，但它功能龐大、原始碼複雜。
這個專案的動機就是「把最常用的那一圈功能親手做出來」：只用 `urllib + ssl + argparse`、
不裝任何套件，藉此搞懂 HTTP 請求／回應、命令列參數設計、以及結束碼與輸出流這些實務細節。
`mycurl2.py` 則是它的超集——直接沿用同一套核心，再把結果包裝成網頁，方便展示與操作。

## 2 · 舉個例子

在 repo 根目錄執行這一行：

```bash
python homework/HW1/mycurl/mycurl.py https://example.com
```

發生了什麼事？

1. mycurl 對 `example.com` 發出 `GET / HTTP/1.1` 請求。
2. 伺服器回傳 `HTTP 200` 加上一份 HTML（body）。
3. mycurl 把 body 原樣印到終端機，你會看到 `<title>Example Domain</title>…`。

就這樣——給 URL，拿回內容。這就是整個專案的核心。

## 3 · 設備需求

- **Python 3.8 以上**，僅此一樣。先檢查版本：`python --version`
- **不用安裝任何套件**：只用標準函式庫（`urllib / ssl / argparse`），沒有 `pip install`，拿到就能跑。
- **作業系統**：Windows / macOS / Linux 都可以。
- **Windows 注意**：如果是 Microsoft Store 帶的假 python，請改去 python.org 安裝正版 Python。

## 4 · 使用方法

基本語法：

```bash
python homework/HW1/mycurl/mycurl.py [選項] URL
```

- **指定方法**：`-X POST`；不指定時，有 `-d` 就是 POST，否則 GET。
- **自訂請求**：`-H "Key: Value"` 加標頭（可重複）；`-d "a=1"` 送資料，`@檔案` 從檔讀；`--json '{"a":1}'` 送 JSON。
- **輸出控制**：預設 body 印到螢幕；`-o 檔名` 存檔；`-i` 連回應標頭一起顯示。
- **除錯與行為**：`-v` 顯示來往過程；`-L` 跟隨重新導向；`--fail` 遇到 HTTP 錯誤回結束碼 22；`-s` 安靜模式。

## 5 · 快速開始（首次操作流程）

1. **開啟終端機**，切換到專案根目錄（能看到 `homework/` 的那層）。
2. **確認 Python**：`python --version`，有印出 3.8 以上就算過關。
3. **跑第一個請求**：`python homework/HW1/mycurl/mycurl.py https://example.com`，看到 HTML 印出來就是成功。
4. **加上選項玩玩看**：`python homework/HW1/mycurl/mycurl.py -v https://httpbin.org/get`
5. **存檔或轉網頁**：
   ```bash
   python homework/HW1/mycurl/mycurl.py -H "X-Token: abc" -i -o out.json https://httpbin.org/get
   python homework/HW1/mycurl/mycurl2.py -i https://example.com --html-out report.html
   ```
6. **完整驗證**：`python -m unittest discover -s homework/HW1/mycurl/tests -v`

## 6 · curl 對照表

| curl | mycurl / mycurl2 | 說明 |
|------|------------------|------|
| `curl URL` | `python mycurl.py URL` | GET 並把 body 印到 stdout |
| `-X POST` | 相同 | 預設有 `-d` 則 POST，否則 GET |
| `-H "K: V"` | 相同（可重複） | 自訂標頭 |
| `-d "a=1"` | 相同，多個用 `&` 接；`@file` 從檔讀 | 請求 body |
| `--json` | `--json '{"a":1}'` | 自動加 JSON Content-Type |
| `-o / -O` | 相同 | 存檔／用遠端檔名存檔 |
| `-i / -v / -L` | 相同 | 含回應標頭／顯示過程／跟隨 3xx（+ `--max-redirs`） |
| `-u / -A / -k / -f / -s` | 相同 | Basic 認證／User-Agent／略過 SSL／失敗回 22／安靜 |

結束碼對齊 curl：`0` 成功 · `2` 參數錯誤 · `7` 連線失敗 · `22` HTTP 錯誤（+`--fail`）·
`23` 寫檔失敗 · `26` 讀檔失敗 · `28` 逾時。

## 7 · mycurl2 多了什麼（超集加值）

`mycurl2.py` 直接 import `mycurl.py` 的核心（parser 繼承、請求共用 `do_request`），
行為保證一致，另加：

- `--html-out FILE`：回應包裝成排版過的 HTML 報告（狀態、請求／回應標頭、內容預覽）。
- `--serve [PORT]`：本機網頁操作介面（只聽 127.0.0.1），瀏覽器填表單、後端發送、結果顯示成網頁。
  ```bash
  python homework/HW1/mycurl/mycurl2.py --serve 8080
  # 開 http://127.0.0.1:8080/
  ```
- `--demo-out FILE`：產生專案介紹頁 `index.html`。

## 8 · 實作重點（報告可寫）

1. 自訂 `NoRedirect(HTTPRedirectHandler)` 擋掉自動導向，自己依 `-L` 手動跟，
   `-v` 才能印出每一站的 `>`／`<`。
2. `HTTPError` 照常回傳 status + body，只有加 `--fail` 才回結束碼 22。
3. body 用 `sys.stdout.buffer` 寫 bytes（圖片／二進位不爛掉）；`-v` 全走 stderr，不污染 pipe／存檔。
4. mycurl2 的 parser 直接繼承 mycurl，請求核心直接呼叫 `do_request`，
   所以「功能一樣」是結構保證，不是口頭保證。

## 9 · 專案結構

```
homework/HW1/mycurl/
  mycurl.py        # 主程式（約 309 行，核心）
  mycurl2.py       # 超集：import mycurl + --html-out/--serve/--demo-out
  index.html       # 介紹頁（雙擊用瀏覽器開；線上版見上方連結）
  mycurl.html      # mycurl.py 原始碼瀏覽頁
  mycurl2.html     # mycurl2.py 原始碼瀏覽頁
  test.sh          # 一鍵檢測腳本
  test-report.txt  # 最新檢測紀錄
  tests/           # 13 個單元測試（本機 http.server，不需外網）
  README.md        # mycurl 詳細文件
```

## 10 · 測試（test.sh）

```bash
bash homework/HW1/mycurl/test.sh 2>&1 | tee homework/HW1/mycurl/test-report.txt
```

最新結果：**PASS=14 FAIL=0，ALL CHECKS PASSED**（含基本指令、13 個單元測試、
實機請求、兩支輸出一致性、`--html-out`、`--serve`），完整過程見 `mycurl/test-report.txt`
（也會自動內嵌進 `index.html` 最底下一節）。
