# HW2：類似金門大學校務系統的專案程式

> Python 為主、純標準函式庫 + sqlite3，老師不需 `pip install` 即可跑。
> 版一（主要功能）放在 `app1/`，之後每加一版就加一個資料夾 `app2, app3...`。
> 靜態展示（免 server、可用連結看）獨立放在 `docs/`，不佔用版本編號。
>
> 線上展示頁：https://yi-ning-huang.github.io/_se/homework/HW2/docs/
> 本機雙擊即看：`docs/index.html`
>
> 個資聲明：本專案所有人名皆為虛構假名，與現實人物無關；
> 課程橫跨多系所，取材自綜合型大學常見開課。

## 版本門檻（你定的規則）
1. 每一版資料夾內都有自己的 `test.sh` + `test-report.txt`（同 HW1 性質）。
2. 該版 `bash test.sh` 出現 `ALL CHECKS PASSED` 才能凍結、複製開下一版。
3. 下一版 `test.sh` 必須含上一版的回歸測試（不能把選課核心改壞）。

執行方式（每版相同）：
```bash
bash homework/HW2/app1/test.sh 2>&1 | tee homework/HW2/app1/test-report.txt
```

## 版本對照
| 版 | 資料夾 | 內容 | 狀態 |
|----|--------|------|------|
| v1.0 主要功能 | `app1/` | 選課核心：登入、課程查詢/搜尋、加選/退選、擋修（額滿/衝堂/學分上限/重複）、我的課表 | PASS=13 FAIL=0，ALL CHECKS PASSED |
| v1.1 | `app2/` | = app1 + 我的成績（分數/等第/加權平均/GPA）+ `/api/grades`，含 app1 回歸 | PASS=13 FAIL=0，ALL CHECKS PASSED |
| v1.2 | `app3/` | = app2 + 老師登分/改分 + 管理員開課，導覽按角色顯示，含回歸 | PASS=13 FAIL=0，ALL CHECKS PASSED |
| 展示（非版本） | `docs/` | 靜態展示頁：雙擊或 Pages 連結可看；`python docs/build.py` 重建 | 已產生 index.html+school.html+app.html |

## app1 快速開始（老師用）
```bash
python homework/HW2/app1/app.py --initdb
python homework/HW2/app1/app.py --serve 8080
# 開 http://127.0.0.1:8080/ ，帳號 s001 密碼 1234
# 免跑 server 也能看：雙擊 homework/HW2/app1/index.html
```
