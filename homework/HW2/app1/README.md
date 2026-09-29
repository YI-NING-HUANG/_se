# HW2 app1：金大校務系統 v1.0（選課核心，主要功能）

> 純 Python 標準函式庫 + sqlite3，不需 `pip install`。
> 本機雙擊即看：`index.html`；要操作：`python app.py --serve 8080` 開 http://127.0.0.1:8080/

## 功能（版一 = 本題本體）
登入/登出、課程查詢+搜尋、加選/退選、擋修（額滿/衝堂/學分上限25/重複）、我的課表。

展示帳號：`s001/s002/s003`，密碼皆 `1234`。

## 快速開始
```bash
python homework/HW2/app1/app.py --initdb
python homework/HW2/app1/app.py --serve 8080
# 開 http://127.0.0.1:8080/ 用 s001/1234 登入
```

## 檢測（每版凍結前必過）
```bash
bash homework/HW2/app1/test.sh 2>&1 | tee homework/HW2/app1/test-report.txt
```
`test-report.txt` 為上次檢測完整輸出，`index.html` 為靜態展示頁。

## 結構
```
app1/
  app.py        # 網頁層 http.server（路由+HTML）
  school.py     # 核心邏輯 sqlite3（選課/擋修，可單測）
  schema.sql    # 三張表 users/courses/enrollments
  tests/        # 9 個單元測試（temp db，不需開 server）
  test.sh / test-report.txt / index.html
```
