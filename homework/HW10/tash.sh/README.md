# tash.sh 測試資料夾

`cafeteria-sim` 的一鍵測試入口。

```bash
bash tash.sh/test.sh
# 或在 HW10 根目錄
bash test.sh
```

測試內容：

1. Python、SimPy、套件匯入與 `compileall`。
2. 35 個 unittest。
3. CLI 黑箱測試：`run`、`compare`、`optimize`、`demo` 的 JSON 內容驗證。
4. `python -m build`、`twine check`、wheel 安裝到暫存目錄後再執行 CLI。

產物：

- `test-report.txt`：完整測試報告。
- `artifacts/unittest.log`：單元測試輸出。
- `artifacts/run.json`、`compare.json`、`optimize.json`：CLI 驗證資料。
- `artifacts/demo.log`：示範輸出。
- `artifacts/build.log`、`twine.log`、`wheel-install.log`：打包與安裝紀錄。

腳本會優先使用 `.venv` 的 Python；也可以用 `PYTHON=/path/to/python bash tash.sh/test.sh`
指定解譯器。建置與 twine 檢查需要 `pip install -e ".[dev]"`。
