# HW2 app3：金大校務系統 v1.2（學生 + 老師 + 管理員）

> 純 Python 標準函式庫 + sqlite3，不需 `pip install`。
> 由 `app2` 凍結複製而來，新增老師/管理員，學生功能全保留（回歸測試涵蓋）。
> 本機雙擊即看：`index.html`；要操作：`python app.py --serve 8080` 開 http://127.0.0.1:8080/

## v1.2 新增（相對 app2）
- 老師（`t001/t002`，密碼 1234）：我的開課 + 點名登分/改分（0~100，只能登自己的課）
- 管理員（`admin`，密碼 admin123）：開課管理（新增課程，擋重複課號）
- 導覽列按角色顯示；跨角色頁面/操作回 403 權限不足

## 功能總覽
學生：登入、課程查詢（科系下拉+搜尋）、加選/退選、擋修、課表、成績。
老師：開課一覽、點名冊登分。管理員：新增課程。

展示帳號：學生 `s001/s002/s003`（1234）、老師 `t001/t002`（1234）、管理員 `admin`（admin123）。

## 快速開始
```bash
python homework/HW2/app3/app.py --initdb
python homework/HW2/app3/app.py --serve 8080
# 開 http://127.0.0.1:8080/ ，用 t001/1234 登入登分看看
```

## 檢測（凍結前必過，含 app2 回歸）
```bash
bash homework/HW2/app3/test.sh 2>&1 | tee homework/HW2/app3/test-report.txt
```

## 結構
```
app3/
  app.py        # 網頁層 http.server（角色路由+HTML）
  school.py     # 核心邏輯 sqlite3（選課/成績/登分/開課，可單測）
  schema.sql    # 三張表 users/courses/enrollments(+score)
  tests/        # 15 個單元測試（temp db，不需開 server）
  test.sh / test-report.txt / index.html
```
