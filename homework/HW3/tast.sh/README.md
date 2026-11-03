# HW3 測試資料夾

這裡集中放置 ForumKeep 的測試入口、測試報告與端到端展示產物。

## 怎麼跑

```bash
# 從專案根目錄
bash test.sh

# 或直接跑本資料夾的腳本
bash tast.sh/test.sh
```

兩個入口等價；根目錄 `test.sh` 只是轉呼叫 `tast.sh/test.sh`。

## 產物

| 路徑 | 說明 |
|------|------|
| `test.sh` | 測試腳本：編譯、36 個單元測試、CLI、端到端封存 |
| `test-report.txt` | 最近一次完整測試輸出與 PASS/FAIL 統計 |
| `artifacts/unittest.log` | unittest 完整輸出 |
| `artifacts/server.log` | 端到端測試用本機 HTTP server 的 log |
| `artifacts/demo/` | 端到端產生的 ForumKeep 封存 |
| `artifacts/demo/site/index.html` | 可直接用瀏覽器打開的離線展示站 |

`artifacts/` 每次執行都會重建；`test-report.txt` 會保留最新結果。

## 測試範圍

1. `python -m compileall`：套件與測試語法檢查。
2. `python -m unittest discover -s tests -v`：單元測試。
3. `python -m forumkeep --version` / `--help`：CLI 入口。
4. 啟動本機 `http.server` 服務 `examples/mini_forum/`，實際執行：
   - `forumkeep run`：crawl + download + build
   - `forumkeep status`
   - `forumkeep verify`
   - 檢查頁面/素材數量、robots 阻擋、離線首頁、搜尋頁、素材庫、manifest、
     未封存連結保留絕對 URL、script 清除、blob 檔案存在。
