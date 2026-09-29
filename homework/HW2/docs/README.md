# HW2 docs：靜態展示頁（獨立於版本資料夾）

> 用連結看：https://yi-ning-huang.github.io/_se/homework/HW2/docs/
> 本機看：雙擊 `index.html`（免網路、免 server）。
> 實際操作（登入/選課）仍需跑 `app1` 的 server。

## 重建
```bash
python homework/HW2/docs/build.py
```
會從 `../app1` 的種子課程 + `test-report.txt` 重新產生
`index.html` + `school.html` + `app.html`。

本資料夾不參與 `app1/app2...` 的 `test.sh` 版本門檻。
