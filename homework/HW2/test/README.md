# HW2 test：測試過程與結果（分門別類）

> 集中跑 `app1/app2/app3` 三版檢測，過程與結果都收在這一層，
> 各版原本的 `appX/test.sh` + `test-report.txt` 保留不動，這裡只是統一入口 + 備份結果。

## 版本對照

| 版 | 程式資料夾 | 測試入口 | 測試過程（腳本） | 測試結果（報告） | 內容 |
|----|------------|----------|------------------|------------------|------|
| v1.0 主要功能 | `../app1/` | `test.sh` | `test.sh` 本體 | `test-report.txt` | 選課核心：登入、查詢/搜尋、加選/退選、擋修（額滿/衝堂/學分上限/重複）、課表 |
| v1.1 | `../app2/` | `test2.sh` | `test2.sh` 本體 | `test-report2.txt` | = v1.0 + 成績（分數/等第/平均/GPA）+ `/api/grades`，含 v1.0 回歸 |
| v1.2 | `../app3/` | `test3.sh` | `test3.sh` 本體 | `test-report3.txt` | = v1.1 + 老師登分/改分 + 管理員開課，導覽按角色顯示，含回歸 |
| 全部 | — | `test-all.sh` | 依序跑 `test.sh` + `test2.sh` + `test3.sh` | 上方三份報告 | 一鍵全測 |

## 怎麼跑

```bash
# 單版
bash homework/HW2/test/test.sh    # v1.0 (app1)
bash homework/HW2/test/test2.sh   # v1.1 (app2)
bash homework/HW2/test/test3.sh   # v1.2 (app3)

# 一次全跑
bash homework/HW2/test/test-all.sh
```

每支 `testX.sh` 都是轉呼叫對應 `../appX/test.sh`，
輸出會同時 `tee` 到對應的 `test-reportX.txt`，所以報告永遠是最新的那次執行。

## 目錄

```
test/
  README.md          # 本檔：版本對照
  test.sh            # v1.0 入口 → ../app1/test.sh
  test2.sh           # v1.1 入口 → ../app2/test.sh
  test3.sh           # v1.2 入口 → ../app3/test.sh
  test-all.sh        # 全測入口
  test-report.txt    # v1.0 結果 (PASS=13, ALL CHECKS PASSED)
  test-report2.txt   # v1.1 結果 (PASS=13, ALL CHECKS PASSED)
  test-report3.txt   # v1.2 結果 (PASS=13, ALL CHECKS PASSED)
```
