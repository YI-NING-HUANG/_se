#!/usr/bin/env python3
"""mycurl2 - 把 mycurl 專案轉成「一看就懂」的展示網頁 (只用 Python 標準函式庫).

性質跟 mycurl.py 一樣: argparse CLI + stdlib only, 雙擊產出的 HTML 就能用瀏覽器開.

用法:
  python homework/HW1/mycurl/mycurl2.py
  python homework/HW1/mycurl/mycurl2.py -o index.html
  python homework/HW1/mycurl/mycurl2.py --source mycurl.py --readme README.md -o index.html
"""

import argparse
import html
import pathlib
import sys

VERSION = "mycurl2 0.1.0 (python stdlib only)"

DEFAULT_SOURCE = pathlib.Path(__file__).with_name("mycurl.py")
DEFAULT_README = pathlib.Path(__file__).with_name("README.md")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mycurl2",
        description="把 mycurl 專案產生為排版過的展示網頁 (index.html)",
    )
    p.add_argument("-o", "--output", default="index.html",
                   help="輸出的 HTML 檔名 (預設 index.html, 與本檔同目錄)")
    p.add_argument("--source", default=str(DEFAULT_SOURCE),
                   help="要內嵌展示的原始碼 (預設 mycurl.py)")
    p.add_argument("--readme", default=str(DEFAULT_README),
                   help="參考的 README (預設 README.md, 目前僅顯示檔名)")
    p.add_argument("--title", default="mycurl — 類似 curl 的專案程式",
                   help="網頁 <title> 與 Hero 標題")
    p.add_argument("--version", action="store_true", help="顯示版本")
    return p


def build_html(source_code: str, title: str) -> str:
    """回傳完整 index.html 字串 (self-contained, file:// 可開)."""
    esc = html.escape(source_code)
    nlines = len(source_code.splitlines())
    # NOTE: CSS/JS 全部 inline, 不用 CDN, 雙擊就能開.
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--bg:#0f172a;--card:#1e293b;--line:#334155;--txt:#e2e8f0;--mut:#94a3b8;--acc:#38bdf8;--acc2:#a78bfa;--ok:#34d399}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:"Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif;background:var(--bg);color:var(--txt);line-height:1.7}}
a{{color:var(--acc)}}
.wrap{{max-width:960px;margin:0 auto;padding:0 20px 80px}}
.hero{{padding:64px 20px 40px;text-align:center;background:radial-gradient(600px 300px at 50% 0%,#1e3a5f,transparent)}}
.badge{{display:inline-block;background:#0ea5e922;border:1px solid var(--acc);color:var(--acc);border-radius:99px;padding:4px 14px;font-size:13px;margin-bottom:14px}}
.hero h1{{font-size:32px;margin:8px 0;color:#fff}}
.hero p{{color:var(--mut);max-width:640px;margin:0 auto}}
.btnrow{{margin-top:20px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.btn{{border:1px solid var(--line);background:var(--card);color:var(--txt);padding:10px 20px;border-radius:10px;cursor:pointer;text-decoration:none;font-size:15px}}
.btn.pri{{background:var(--acc);border-color:var(--acc);color:#082f49;font-weight:700}}
.grid3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:28px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.card h3{{margin:0 0 6px;font-size:17px}}
.card p{{margin:0;color:var(--mut);font-size:14px}}
h2{{margin:48px 0 12px;font-size:22px;border-left:5px solid var(--acc);padding-left:12px}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:var(--card);border-radius:12px;overflow:hidden}}
th,td{{border-bottom:1px solid var(--line);padding:9px 10px;text-align:left;vertical-align:top}}
th{{background:#0ea5e918;color:#fff}}
code,.cmd{{font-family:Consolas,Menlo,monospace}}
.cmd{{background:#020617;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:10px 0;font-size:13.5px;position:relative;overflow-x:auto;white-space:pre}}
.cmd button{{position:absolute;right:8px;top:8px;font-size:12px;border-radius:8px;border:1px solid var(--line);background:#0f172a;color:var(--txt);padding:3px 10px;cursor:pointer}}
.flow{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;font-size:14px}}
.flow b{{background:#020617;border:1px solid var(--line);border-radius:8px;padding:6px 12px}}
.flow span{{color:var(--acc)}}
ol.tight li{{margin-bottom:6px}}
pre.src{{background:#020617;border:1px solid var(--line);border-radius:12px;padding:16px;overflow:auto;font-size:12.5px;line-height:1.55;max-height:520px}}
details{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px}}
summary{{cursor:pointer;font-weight:700}}
.foot{{margin-top:56px;color:var(--mut);font-size:13px;text-align:center;border-top:1px solid var(--line);padding-top:18px}}
.tag{{display:inline-block;font-size:12px;background:#020617;border:1px solid var(--line);border-radius:6px;padding:1px 8px;margin:2px}}
.kbd{{background:#020617;border:1px solid var(--line);border-bottom-width:2px;border-radius:6px;padding:0 7px;font-family:monospace}}
</style>
</head>
<body>
<div class="hero">
  <div class="badge">HW1 專案 · 請做一個類似 curl 的程式 (可用 AI · opencode + Big Pickle)</div>
  <h1>{html.escape(title)}</h1>
  <p>只用 <b>Python 標準函式庫</b> 的最小可用版 curl：GET / POST / 標頭 / 存檔 / 導向 / 認證，一看就懂，雙擊即用。</p>
  <div class="btnrow">
    <a class="btn pri" href="#quick">快速開始</a>
    <a class="btn" href="#compare">curl 對照表</a>
    <a class="btn" href="#src">看完整原始碼 ({nlines} 行)</a>
  </div>
</div>
<div class="wrap">

  <div class="grid3">
    <div class="card"><h3>📦 零依賴</h3><p>只用 <code>urllib + ssl + argparse</code>，不用 <code>pip install</code>，Windows / macOS / Linux 都能跑。</p></div>
    <div class="card"><h3>🔁 對齊 curl</h3><p>參數與結束碼對齊 curl：<span class="tag">-X</span><span class="tag">-H</span><span class="tag">-d</span><span class="tag">-o/-O</span><span class="tag">-i/-v/-L</span><span class="tag">--fail</span>，學會 curl 就會 mycurl。</p></div>
    <div class="card"><h3>🤖 AI 開發</h3><p>用 <b>opencode + Big Pickle / Muse Spark</b> 產生 + 人工審查，plan → build → <code>unittest</code> 驗證。</p></div>
  </div>

  <h2>1 · 它在做什麼？（30 秒看懂）</h2>
  <div class="flow"><b>你</b><span>→</span><b>mycurl.py URL -v -L</b><span>→</span><b>Internet (http/https)</b><span>→</span><b>印出 body / 存檔</b></div>
  <ul>
    <li><b>輸入：</b>URL + 選項（方法、標頭、資料、存檔、除錯）</li>
    <li><b>處理：</b>組 request → 擋自動導向、需要才手動跟 <span class="kbd">-L</span> → 讀 status + headers + body</li>
    <li><b>輸出：</b>body 走 <code>stdout</code>（可 pipe / <span class="kbd">-o</span> 存檔），過程走 <code>stderr</code>（<span class="kbd">-v</span> 不污染存檔）</li>
  </ul>

  <h2 id="compare">2 · curl 對照表</h2>
  <table>
    <tr><th>curl</th><th>mycurl</th><th>說明</th></tr>
    <tr><td><code>curl URL</code></td><td><code>python mycurl.py URL</code></td><td>GET 並把 body 印到 stdout</td></tr>
    <tr><td><code>-X POST</code></td><td>相同</td><td>預設有 <code>-d</code> 則 POST，否則 GET</td></tr>
    <tr><td><code>-H "K: V"</code></td><td>相同（可重複）</td><td>自訂標頭</td></tr>
    <tr><td><code>-d "a=1"</code></td><td>相同，多個用 <code>&amp;</code> 接；<code>@file</code> 從檔讀</td><td>請求 body</td></tr>
    <tr><td><code>--json</code></td><td><code>--json '{{"a":1}}'</code></td><td>自動加 JSON Content-Type</td></tr>
    <tr><td><code>-o / -O</code></td><td>相同</td><td>存檔 / 用遠端檔名存檔</td></tr>
    <tr><td><code>-i / -v / -L</code></td><td>相同</td><td>含回應標頭 / 顯示過程 / 跟隨 3xx（+ <code>--max-redirs</code>）</td></tr>
    <tr><td><code>-u / -A / -k / -f / -s</code></td><td>相同</td><td>Basic 認證 / User-Agent / 略過 SSL / 失敗回 22 / 安靜</td></tr>
  </table>
  <p style="color:var(--mut);font-size:13px">結束碼對齊 curl：0 成功 · 2 參數錯誤 · 7 連線失敗 · 22 HTTP 錯誤(+--fail) · 23 寫檔失敗 · 26 讀檔失敗 · 28 逾時</p>

  <h2 id="quick">3 · 快速開始（複製即用）</h2>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py https://example.com<button onclick="copy(this)">複製</button></div>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py -v https://httpbin.org/get<button onclick="copy(this)">複製</button></div>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py -d "a=1&amp;b=2" https://httpbin.org/post<button onclick="copy(this)">複製</button></div>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py --json '{{"hello":"world"}}' https://httpbin.org/post<button onclick="copy(this)">複製</button></div>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py -H "X-Token: abc" -i -o out.json https://httpbin.org/get<button onclick="copy(this)">複製</button></div>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py -L -v http://github.com<button onclick="copy(this)">複製</button></div>
  <div class="cmd">python -m unittest discover -s homework/HW1/mycurl/tests -v<button onclick="copy(this)">複製</button></div>

  <h2>4 · 實作重點（報告可寫）</h2>
  <ol class="tight">
    <li>自訂 <code>NoRedirect(HTTPRedirectHandler)</code> 擋掉自動導向，自己依 <code>-L</code> 手動跟，<code>-v</code> 才能印出每一站的 <code>&gt;</code> / <code>&lt;</code>。</li>
    <li><code>HTTPError</code> 照常回傳 status + body，只有加 <code>--fail</code> 才回結束碼 22。</li>
    <li>body 用 <code>sys.stdout.buffer</code> 寫 bytes（圖片/二進位不爛掉）；<code>-v</code> 全走 stderr，不污染 pipe / 存檔。</li>
    <li>本頁就是用 <code>mycurl2.py</code>（同為 stdlib CLI）產生的：改完 <code>mycurl.py</code> 再跑一次即更新 HTML，保證「之後的更改也能用 HTML 開」。</li>
  </ol>
  <div class="cmd">python homework/HW1/mycurl/mycurl2.py -o homework/HW1/mycurl/index.html<button onclick="copy(this)">複製</button></div>

  <h2>5 · AI 使用說明（opencode + Big Pickle）</h2>
  <ol class="tight">
    <li>在專案目錄跑 <code>opencode</code>，模型選 Big Pickle（免費）或 Muse。</li>
    <li>先 plan 模式：「用 Python 標準函式庫做 curl 最小可用版，列出參數表」。</li>
    <li>再 build 模式實作，跑 <code>python -m unittest</code> 驗證（13 個測試，本機 http.server，不需外網）。</li>
    <li>本次即用 Muse Spark 按此流程完成，報告註明模型與日期即可。</li>
  </ol>

  <h2>6 · 專案結構</h2>
  <div class="cmd">homework/HW1/mycurl/
  mycurl.py      # 主程式 (約 {nlines} 行)
  mycurl2.py  # 本頁產生器 (stdlib CLI, 重新產生 HTML 用)
  index.html     # 本頁 (雙擊用瀏覽器開)
  mycurl.html    # mycurl.py 純碼版
  tests/         # 13 個測試</div>

  <h2 id="src">7 · 完整原始碼（mycurl.py）</h2>
  <details open>
    <summary>點我展開 / 收合 · 共 {nlines} 行</summary>
    <pre class="src"><code>{esc}</code></pre>
  </details>

  <div class="foot">mycurl · HW1 · 類似 curl 的專案程式 · 用 opencode + Big Pickle / Muse Spark 開發 · Python 標準函式庫 only</div>
</div>
<script>
function copy(btn){{
  var t = btn.parentNode.firstChild.textContent;
  function done(){{btn.textContent='已複製';setTimeout(function(){{btn.textContent='複製'}},1200)}}
  if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(t).then(done).catch(function(){{fallback()}})}}else{{fallback()}}
  function fallback(){{var ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();try{{document.execCommand('copy');done()}}catch(e){{}}document.body.removeChild(ta)}}
}}
</script>
</body>
</html>"""


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(VERSION)
        return 0

    src_path = pathlib.Path(args.source)
    if not src_path.is_file():
        print(f"mycurl2: 找不到原始碼: {src_path}", file=sys.stderr)
        return 2
    try:
        code = src_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"mycurl2: 讀取失敗: {e}", file=sys.stderr)
        return 23

    out_path = pathlib.Path(args.output)
    if not out_path.is_absolute():
        # 預設寫到本檔同目錄, 方便放在 HW1/mycurl 底下
        out_path = pathlib.Path(__file__).with_name(out_path.name)

    page = build_html(code, args.title)
    try:
        out_path.write_text(page, encoding="utf-8")
    except OSError as e:
        print(f"mycurl2: 寫入失敗: {e}", file=sys.stderr)
        return 23

    print(f"已產生 {out_path} ({len(page)} chars, 內嵌 {len(code.splitlines())} 行原始碼)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
