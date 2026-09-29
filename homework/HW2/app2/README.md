# HW2 app2：金大校務系統 v1.1（選課核心 + 成績查詢/GPA）

> 純 Python 標準函式庫 + sqlite3，不需 `pip install`。
> 由 `app1` 凍結複製而來，新增成績功能，舊功能全保留（回歸測試涵蓋）。
> 本機雙擊即看：`index.html`；要操作：`python app.py --serve 8080` 開 http://127.0.0.1:8080/

## v1.1 新增（相對 app1）
- 我的成績頁：各科分數 + 等第（4.0 制）+ 學分加權平均 + GPA
- 展示帳號 `s001/s002/s003` 都有預設成績可直接看（登入任一個，選課+成績都能用）
- 新 API：`/api/grades?sid=s003`

## 功能總覽
登入/登出、課程查詢（科系下拉+搜尋）、加選/退選、擋修（額滿/衝堂/學分上限25/重複）、我的課表、我的成績。

展示帳號：`s001/s002/s003`，密碼皆 `1234`。

## 快速開始
```bash
python homework/HW2/app2/app.py --initdb
python homework/HW2/app2/app.py --serve 8080
# 開 http://127.0.0.1:8080/ 用 s003/1234 登入看成績
```

## 檢測（凍結前必過，含 app1 回歸）
```bash
bash homework/HW2/app2/test.sh 2>&1 | tee homework/HW2/app2/test-report.txt
```

## 結構
```
app2/
  app.py        # 網頁層 http.server（路由+HTML）
  school.py     # 核心邏輯 sqlite3（選課/擋修/成績GPA，可單測）
  schema.sql    # 三張表 users/courses/enrollments(+score)
  tests/        # 12 個單元測試（temp db，不需開 server）
  test.sh / test-report.txt / index.html
```
