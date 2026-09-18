# 課程：現代軟體工程 -- 學生作業與專案

欄位 | 內容
-----|--------
學期 | 115 學年上學期
教師 | [陳鍾誠](https://www.nqu.edu.tw/educsie/index.php?act=blog&code=list&ids=4)
學校 | [金門大學資訊工程系](https://www.nqu.edu.tw/educsie/index.php)
學生 | xxx
學號 | xx

## HW1: mycurl — 類似 curl 的最小可用版 (Python 標準函式庫)

本資料夾為 HW1 作業內容, 實作放在 `mycurl/` 子目錄, 詳細用法見 [mycurl/README.md](mycurl/README.md)。

* 主程式: `mycurl/mycurl.py` (GET/POST/`-H`/`-d`/`-o`/`-i`/`-v`/`-L` 等, 零依賴)
* 測試: `mycurl/tests/test_mycurl.py` (13 個測試, 本機 `http.server`, 不需外網)

```bash
# 在 repo 根目錄執行
python homework/HW1/mycurl/mycurl.py https://example.com
python -m unittest discover -s homework/HW1/mycurl/tests -v
```
