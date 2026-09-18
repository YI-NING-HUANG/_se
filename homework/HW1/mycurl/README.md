# mycurl — 類似 curl 的最小可用版 (Python 標準函式庫)

> 作業/專案用: 只用 Python 標準函式庫, 不用 `pip install`, Windows / macOS / Linux 都能跑。
> 開發方式: 用 AI (Muse / OpenCode + Big Pickle 皆可) 輔助產生 + 人工審查。

## 功能對照 curl

| curl | mycurl | 說明 |
|------|--------|------|
| `curl URL` | `python homework/HW1/mycurl/mycurl.py URL` | GET 並把 body 印到 stdout |
| `-X POST` | 相同 | 指定方法, 預設有 `-d` 則 POST 否則 GET |
| `-H "K: V"` | 相同 | 可重複, 例 `-H "X-Token: abc" -H "A: B"` |
| `-d "a=1"` | 相同 | 多個 `-d` 用 `&` 連接; `@file` 從檔讀 |
| `--json` (curl 無, 但 httpie 有) | `mycurl --json '{"a":1}'` | 自動加 `Content-Type: application/json` |
| `-o file` | 相同 | 存到檔案 |
| `-O` | 相同 | 用 URL 最後一段當檔名 |
| `-i` | 相同 | 輸出包含回應標頭 |
| `-v` | 相同 | 請求/回應過程印到 stderr (`> `/`< `) |
| `-L` | 相同 | 跟隨 3xx, 搭配 `--max-redirs 5` |
| `--timeout` | `--timeout 10` | 逾時秒數 |
| `-u user:pass` | 相同 | Basic 認證 |
| `-A "..."` | 相同 | User-Agent |
| `-k` | 相同 | 略過 SSL 驗證 |
| `-f/--fail` | 相同 | HTTP>=400 時結束碼 22 且不輸出 body |
| `-s` | 相同 | 安靜模式 |

結束碼對齊 curl: `0` 成功, `2` 參數錯誤, `7` 連線失敗, `22` HTTP 錯誤(+`--fail`),
`23` 寫檔失敗, `26` 讀資料檔失敗, `28` 逾時。

## 快速開始

需要 Python 3.8+ (本機若只有 Microsoft Store 假 python, 請先到 python.org 安裝正版 Python)。

```bash
# 1. 最簡單 GET (以下皆在 repo 根目錄執行)
python homework/HW1/mycurl/mycurl.py https://example.com

# 2. 顯示過程 (像是 curl -v)
python homework/HW1/mycurl/mycurl.py -v https://httpbin.org/get

# 3. POST 表單
python homework/HW1/mycurl/mycurl.py -d "a=1&b=2" https://httpbin.org/post

# 4. POST JSON
python homework/HW1/mycurl/mycurl.py --json "{\"hello\":\"world\"}" https://httpbin.org/post

# 5. 自訂標頭 + 存檔 + 含回應標頭
python homework/HW1/mycurl/mycurl.py -H "X-Token: abc" -i -o out.json https://httpbin.org/get

# 6. 跟隨導向
python homework/HW1/mycurl/mycurl.py -L -v http://github.com

# 7. Basic 認證
python homework/HW1/mycurl/mycurl.py -u user:pass https://httpbin.org/basic-auth/user/pass
```

Windows (PowerShell) 注意引號:

```powershell
python homework/HW1/mycurl/mycurl.py --json '{\"hello\":\"world\"}' https://httpbin.org/post
python homework/HW1/mycurl/mycurl.py -H 'X-Token: abc' https://httpbin.org/get
```

## 跑測試 (在 repo 根目錄執行)

```bash
python -m unittest discover -s homework/HW1/mycurl/tests -v
# 或
python homework/HW1/mycurl/tests/test_mycurl.py
```

測試會在本機開一個 `http.server` (127.0.0.1 隨機 port),
驗證 GET / POST / 標頭 / 導向 / 404 / `-o` 存檔 / `--fail`, 不需外網。

## 專案結構

```
homework/HW1/mycurl/
  mycurl.py        # 主程式 (argparse + urllib, 約 300 行)
  __init__.py      # package 版本
  requirements.txt # 空的, 證明零依賴
  tests/
    test_mycurl.py # 13 個測試
  README.md        # 本檔
```

## 實作重點 (報告可寫)

1. 只用 `urllib.request` + `ssl` + `argparse`, 不依賴 `requests`, 方便交作業。
2. 用自訂 `NoRedirect(HTTPRedirectHandler)` 擋掉自動導向,
   自己依 `-L` 手動跟隨, 這樣 `-v` 才能印出每一站的 `> `/`< `。
3. `HTTPError` 照常回傳 status+body, 只有加 `--fail` 才回結束碼 22 (對齊 curl)。
4. 輸出用 `sys.stdout.buffer` 寫 bytes, 圖片/二進位也不會爛掉;
   `-v` 過程一律走 stderr, 才不會污染 `-o` / pipe 的 body。

## AI 使用說明 (opencode / Big Pickle / Muse)

此專案可用任何 AI 模型產生, 建議流程:

1. `opencode` 在專案目錄跑起來, 模型選 Big Pickle (免費) 或 Muse。
2. 先 plan 模式: 「用 Python 標準函式庫做 curl 最小可用版, 列出參數表」。
3. 再 build 模式實作, 跑 `python -m unittest` 驗證。
4. 本次即用 Muse Spark 按此流程完成, 你可以在報告中註明模型與日期。

## 之後可加 (進階版 ideas)

- 下載進度條 (`Content-Length` + stderr `#` 條)
- `--retry N` + 間隔重試
- `PUT/DELETE/PATCH` 檔案上傳 (`-d @file` 已支援一半)
- AI 加值: `--explain` 把回應丟給 LLM 自動解說
