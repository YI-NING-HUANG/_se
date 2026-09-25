#!/usr/bin/env python3
"""mycurl2 - mycurl 的超集 (只用 Python 標準函式庫).

以 mycurl.py 當基礎: 直接 import 它的核心函式, 所以全部 mycurl 功能
(URL/-X/-H/-d/--json/-o/-O/-i/-v/-L/--timeout/-u/-A/-k/--fail/-s)
在 mycurl2 一字不差都能用, 行為與結束碼完全一致.

多出來的網頁加值 (把結果以網頁 HTTP 形式顯現):
  --html-out FILE  把本次回應包裝成排版過的 HTML 報告存檔 (瀏覽器可開)
  --serve [PORT]   啟動本機網頁操作介面 (瀏覽器填表單 -> 後端發請求 -> 結果顯示在網頁上)
  --demo-out FILE  產生專案介紹頁 index.html (舊功能保留)

用法:
  python homework/HW1/mycurl/mycurl2.py https://example.com          # 跟 mycurl.py 一樣
  python homework/HW1/mycurl/mycurl2.py -i URL --html-out r.html     # 回應另存成網頁報告
  python homework/HW1/mycurl/mycurl2.py --serve 8080                 # 開 http://127.0.0.1:8080/
  python homework/HW1/mycurl/mycurl2.py --demo-out index.html        # 產生介紹頁
"""

import argparse
import html
import os
import pathlib
import sys
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---- 以 mycurl.py 當基礎: 把 HW1 目錄放上 sys.path, 直接拿它的函式來用 ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_HW1 = os.path.dirname(_HERE)
if _HW1 not in sys.path:
    sys.path.insert(0, _HW1)
try:
    import mycurl.mycurl as _base
    from mycurl.mycurl import (
        do_request,
        load_data,
        make_ssl_context,
        parse_header,
        resolve_output_path,
    )
except ImportError as e:  # pragma: no cover
    print(f"mycurl2: 載入 mycurl.py 失敗 (需要跟 mycurl.py 同目錄): {e}",
          file=sys.stderr)
    sys.exit(2)

VERSION = "mycurl2 0.2.0 (superset of " + _base.VERSION + ")"

DEFAULT_SOURCE = pathlib.Path(__file__).with_name("mycurl.py")
REPORT_BODY_LIMIT = 100000  # HTML 報告最多內嵌幾個字元的 body 預覽
SERVE_TIMEOUT_CAP = 30      # --serve 後端發請求的逾時上限(秒)


def build_parser() -> argparse.ArgumentParser:
    # 直接拿 mycurl 的 parser, 全部參數原樣繼承 (保證功能一字不差)
    p = _base.build_parser()
    p.prog = "mycurl2"
    p.description = "mycurl 的超集: 全部 mycurl 功能 + 輸出成網頁 / 本機網頁操作介面"
    g = p.add_argument_group("mycurl2 網頁加值")
    g.add_argument("--html-out", default=None, metavar="FILE",
                   help="把本次回應包裝成排版過的 HTML 報告存檔 (瀏覽器可開, 可與 -o 並用)")
    g.add_argument("--serve", nargs="?", const=8080, default=None, type=int,
                   metavar="PORT",
                   help="啟動本機網頁操作介面 (預設 port 8080, 只聽 127.0.0.1)")
    g.add_argument("--demo-out", default=None, metavar="FILE",
                   help="產生專案介紹頁 (例: --demo-out index.html)")
    g.add_argument("--source", default=str(DEFAULT_SOURCE),
                   help="介紹頁要內嵌的原始碼 (預設 mycurl.py)")
    g.add_argument("--title", default="mycurl — 類似 curl 的專案程式",
                   help="介紹頁 <title> 與 Hero 標題")
    return p


# ---------------------------------------------------------------- 網頁報告

def _body_preview(data: bytes):
    """回傳 (is_text, preview_str). 二進位不直接顯示."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False, ""
    if len(text) > REPORT_BODY_LIMIT:
        return True, text[:REPORT_BODY_LIMIT] + f"\n…(以下省略, 全文 {len(data)} bytes)"
    return True, text


def build_report_html(url, method, req_headers, status, resp_headers, data,
                      final_url) -> str:
    """把一次請求/回應包裝成排版過的 HTML (self-contained, file:// 可開)."""
    if status < 300:
        cls, label = "ok", "成功"
    elif status < 400:
        cls, label = "redir", "重新導向"
    else:
        cls, label = "err", "錯誤"
    is_text, preview = _body_preview(data)
    if is_text:
        body_html = f"<pre>{html.escape(preview) or '(空 body)'}</pre>"
    else:
        body_html = f"<p>二進位內容不直接顯示 (共 {len(data)} bytes)。</p>"
    req_rows = "".join(f"<tr><td><code>{html.escape(k)}</code></td>"
                       f"<td><code>{html.escape(v)}</code></td></tr>"
                       for k, v in req_headers) or "<tr><td colspan=2>(無)</td></tr>"
    resp_rows = "".join(f"<tr><td><code>{html.escape(k)}</code></td>"
                        f"<td><code>{html.escape(v)}</code></td></tr>"
                        for k, v in resp_headers) or "<tr><td colspan=2>(無)</td></tr>"
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>mycurl2 報告 · {method} {html.escape(final_url)} · {status}</title>
<style>
body{{font-family:"Microsoft JhengHei",system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;line-height:1.7}}
.wrap{{max-width:900px;margin:0 auto;padding:24px 20px 60px}}
h1{{font-size:20px}}h2{{font-size:17px;border-left:5px solid #38bdf8;padding-left:10px}}
.card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:14px 16px;margin:12px 0}}
.ok{{color:#34d399}}.redir{{color:#fbbf24}}.err{{color:#f87171}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
th,td{{border-bottom:1px solid #334155;padding:6px 8px;text-align:left;vertical-align:top;word-break:break-all}}
code,pre{{font-family:Consolas,Menlo,monospace}}
pre{{background:#020617;border:1px solid #334155;border-radius:10px;padding:12px;overflow:auto;max-height:480px;white-space:pre-wrap}}
.foot{{color:#94a3b8;font-size:12px;margin-top:24px}}
</style>
</head>
<body><div class="wrap">
<h1>mycurl2 回應報告 <span class="{cls}">HTTP {status} · {label}</span></h1>
<div class="card"><b>{html.escape(method)}</b> {html.escape(url)}
<br>最終 URL: {html.escape(final_url)}<br>body 大小: {len(data)} bytes</div>
<h2>請求標頭</h2><div class="card"><table>{req_rows}</table></div>
<h2>回應標頭</h2><div class="card"><table>{resp_rows}</table></div>
<h2>回應內容</h2><div class="card">{body_html}</div>
<div class="foot">由 mycurl2 產生 ({html.escape(VERSION)}) · 與 mycurl.py 相同核心發送</div>
</div></body></html>"""


# ---------------------------------------------------------------- 本機網頁介面

_FORM = """<!DOCTYPE html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>mycurl2 web</title>
<style>
body{{font-family:"Microsoft JhengHei",system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0}}
.wrap{{max-width:720px;margin:0 auto;padding:32px 20px}}
label{{display:block;margin:12px 0 4px;color:#94a3b8}}
input[type=text],input[type=number],textarea,select{{width:100%;background:#020617;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:8px}}
button{{margin-top:16px;background:#38bdf8;border:0;border-radius:10px;padding:10px 26px;font-size:16px;font-weight:700;cursor:pointer}}
</style></head>
<body><div class="wrap">
<h1>mycurl2 web — 瀏覽器版 curl</h1>
<p style="color:#94a3b8">填表單 → 後端用 mycurl 核心發請求 → 結果顯示成網頁 (只聽 127.0.0.1, 僅 http/https)</p>
<form method="get" action="/fetch">
<label>URL</label><input type="text" name="url" value="https://example.com" required>
<label>方法</label><select name="method"><option>GET</option><option>POST</option></select>
<label>標頭 (一行一個 Key: Value)</label><textarea name="headers" rows="3"></textarea>
<label>傳送資料 (POST 用)</label><textarea name="data" rows="3"></textarea>
<label><input type="checkbox" name="follow" checked> 跟隨重新導向 (-L)</label>
<button type="submit">發送請求</button>
</form></div></body></html>"""


class _WebHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, page: str):
        raw = page.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/fetch":
            self._handle_fetch(urllib.parse.parse_qs(parsed.query))
        else:
            self._send(200, _FORM)

    def _handle_fetch(self, qs):
        url = (qs.get("url") or [""])[0]
        method = ((qs.get("method") or ["GET"])[0] or "GET").upper()
        if method not in ("GET", "POST"):
            self._send(400, "<h1>只支援 GET/POST</h1>")
            return
        if not url.startswith(("http://", "https://")):
            self._send(400, "<h1>只支援 http/https URL</h1>")
            return
        headers = []
        for line in (qs.get("headers") or [""])[0].splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                headers.append(parse_header(line))
            except ValueError as e:
                self._send(400, f"<h1>標頭格式錯誤</h1><p>{html.escape(str(e))}</p>")
                return
        data = (qs.get("data") or [""])[0].encode("utf-8") or None
        if data is not None and method == "GET":
            method = "POST"
        headers = [h for h in headers
                   if h[0].lower() not in ("user-agent", "content-length")]
        headers.append(("User-Agent", "mycurl2-web/0.2.0"))
        if data is not None:
            headers.append(("Content-Length", str(len(data))))
        follow = "follow" in qs
        try:
            status, resp_headers, body, final = do_request(
                url, method, headers, data, SERVE_TIMEOUT_CAP, None,
                follow, 5, False)
        except Exception as e:  # 連線失敗等一律轉 502 頁
            self._send(502, f"<h1>請求失敗</h1><p>{html.escape(str(e))}</p>")
            return
        self._send(status if status < 500 else 200,
                   build_report_html(url, method, headers, status,
                                     resp_headers, body, final))

    def log_message(self, *args):  # 安靜, 不洗版面
        pass


def run_serve(port: int) -> int:
    try:
        httpd = HTTPServer(("127.0.0.1", port), _WebHandler)
    except OSError as e:
        print(f"mycurl2: 啟動 web 介面失敗 (port {port}): {e}", file=sys.stderr)
        return 7
    print(f"mycurl2 web: http://127.0.0.1:{port}/ (Ctrl+C 結束, 只聽本機)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


# ---------------------------------------------------------------- 介紹頁 (舊功能保留)

def build_showcase_html(source_code: str, title: str, report_text: str = "") -> str:
    """回傳專案介紹頁 (self-contained, file:// 可開)."""
    import re
    esc = html.escape(source_code)
    nlines = len(source_code.splitlines())
    m = re.search(r"結果: PASS=(\d+) FAIL=(\d+)", report_text)
    summary = f"PASS={m.group(1)} FAIL={m.group(2)}" if m else "尚無紀錄"
    report_esc = (html.escape(report_text) if report_text
                  else "(尚無 test-report.txt，請先跑 bash homework/HW1/mycurl/test.sh)")
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--bg:#0f172a;--card:#1e293b;--line:#334155;--txt:#e2e8f0;--mut:#94a3b8;--acc:#38bdf8}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:"Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif;background:var(--bg);color:var(--txt);line-height:1.7}}
a{{color:var(--acc)}}
.wrap{{max-width:960px;margin:0 auto;padding:0 20px 80px}}
.hero{{padding:64px 20px 40px;text-align:center;background:radial-gradient(600px 300px at 50% 0%,#1e3a5f,transparent)}}
.badge{{display:inline-block;background:#0ea5e922;border:1px solid var(--acc);color:var(--acc);border-radius:99px;padding:4px 14px;font-size:13px;margin-bottom:14px}}
.hero h1{{font-size:32px;margin:8px 0;color:#fff}}
.hero p{{color:var(--mut);max-width:640px;margin:0 auto}}
.btnrow{{margin-top:20px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.btn{{border:1px solid var(--line);background:var(--card);color:var(--txt);padding:10px 20px;border-radius:10px;text-decoration:none;font-size:15px}}
.btn.pri{{background:var(--acc);border-color:var(--acc);color:#082f49;font-weight:700}}
.grid3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:28px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.card h3{{margin:0 0 6px;font-size:17px}}
.card p{{margin:0;color:var(--mut);font-size:14px}}
h2{{margin:48px 0 12px;font-size:22px;border-left:5px solid var(--acc);padding-left:12px}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:var(--card)}}
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
.steps{{margin:18px 0;padding:0;list-style:none;counter-reset:st}}
.steps li{{position:relative;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px 14px 62px;margin:0 0 12px}}
.steps li::before{{counter-increment:st;content:counter(st);position:absolute;left:16px;top:14px;width:32px;height:32px;border-radius:50%;background:var(--acc);color:#082f49;font-weight:800;display:flex;align-items:center;justify-content:center;font-size:15px}}
.ex{{background:#020617;border:1px solid var(--line);border-radius:10px;padding:12px;font-size:13px;overflow-x:auto;white-space:pre;margin:10px 0;color:#a5f3c7}}
.req{{color:var(--mut);font-size:14px}}
</style>
</head>
<body>
<div class="hero">
  <div class="badge">HW1 作業 · 做一個類似 curl 的程式</div>
  <h1>{html.escape(title)}</h1>
  <p>只用 <b>Python 標準函式庫</b> 的最小可用版 curl：<code>mycurl.py</code> 發請求，
  <code>mycurl2.py</code> 是它的超集——功能完全一樣，再加網頁呈現。</p>
  <div class="btnrow">
    <a class="btn pri" href="#intro">專案簡介</a>
    <a class="btn" href="#example">看範例</a>
    <a class="btn" href="#quick">快速開始</a>
    <a class="btn" href="#src">看完整原始碼 ({nlines} 行)</a>
  </div>
</div>
<div class="wrap">

  <div class="grid3">
    <div class="card"><h3>📦 零依賴</h3><p>只用 <code>urllib + ssl + argparse</code>，不用 <code>pip install</code>，Windows / macOS / Linux 都能跑。</p></div>
    <div class="card"><h3>🔁 對齊 curl</h3><p>參數與結束碼對齊 curl：<span class="tag">-X</span><span class="tag">-H</span><span class="tag">-d</span><span class="tag">-o/-O</span><span class="tag">-i/-v/-L</span><span class="tag">--fail</span>，學會 curl 就會 mycurl。</p></div>
    <div class="card"><h3>🌐 mycurl2 超集</h3><p>直接 import mycurl 核心，行為保證一致，另加 <span class="tag">--html-out</span><span class="tag">--serve</span> 把結果變成網頁。</p></div>
  </div>

  <h2 id="intro">1 · 專案簡介（動機與介紹）</h2>
  <p><b>mycurl</b> 是一個「最小可用版的 curl」：用<b>純 Python 標準函式庫</b>寫成的命令列 HTTP 客戶端。你在終端機給它 URL 和選項，它就發出 HTTP 請求，把伺服器回傳的內容印出來或存成檔案。</p>
  <p><b>為什麼做這個？</b>curl 是每個工程師都會用到的網路工具，但它功能龐大、原始碼複雜。這個專案的動機就是「把最常用的那一圈功能親手做出來」：只用 <code>urllib + ssl + argparse</code>、不裝任何套件，藉此搞懂 HTTP 請求/回應、命令列參數設計、以及結束碼與輸出流這些實務細節。<code>mycurl2.py</code> 則是它的超集——直接沿用同一套核心，再把結果包裝成網頁，方便展示與操作。</p>

  <h2 id="example">2 · 舉個例子</h2>
  <p>在 repo 根目錄執行這一行：</p>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py https://example.com<button onclick="copy(this)">複製</button></div>
  <p>發生了什麼事？</p>
  <ol class="tight">
    <li>mycurl 對 <code>example.com</code> 發出 <code>GET / HTTP/1.1</code> 請求。</li>
    <li>伺服器回傳 <code>HTTP 200</code> 加上一份 HTML（body）。</li>
    <li>mycurl 把 body 原樣印到終端機，你會看到：</li>
  </ol>
  <div class="ex">&lt;!doctype html&gt;
&lt;html&gt;
&lt;head&gt;&lt;title&gt;Example Domain&lt;/title&gt;…</div>
  <p class="req">就這樣——給 URL，拿回內容。這就是整個專案的核心。</p>

  <h2 id="req">3 · 設備需求</h2>
  <ul>
    <li><b>Python 3.8 以上</b>，僅此一樣。先檢查版本：</li>
  </ul>
  <div class="cmd">python --version<button onclick="copy(this)">複製</button></div>
  <ul>
    <li><b>不用安裝任何套件</b>：只用標準函式庫（<code>urllib / ssl / argparse</code>），沒有 <code>pip install</code>，拿到就能跑。</li>
    <li><b>作業系統</b>：Windows / macOS / Linux 都可以。</li>
    <li><b>Windows 注意</b>：如果是 Microsoft Store 帶的假 python，請改去 python.org 安裝正版 Python。</li>
  </ul>

  <h2 id="usage">4 · 使用方法</h2>
  <p>基本語法：</p>
  <div class="cmd">python homework/HW1/mycurl/mycurl.py [選項] URL<button onclick="copy(this)">複製</button></div>
  <ul>
    <li><b>指定方法</b>：<code>-X POST</code>；不指定時，有 <code>-d</code> 就是 POST，否則 GET。</li>
    <li><b>自訂請求</b>：<code>-H "Key: Value"</code> 加標頭（可重複）；<code>-d "a=1"</code> 送資料，<code>@檔案</code> 從檔讀；<code>--json '{{"a":1}}'</code> 送 JSON。</li>
    <li><b>輸出控制</b>：預設 body 印到螢幕；<code>-o 檔名</code> 存檔；<code>-i</code> 連回應標頭一起顯示。</li>
    <li><b>除錯與行為</b>：<code>-v</code> 顯示來往過程；<code>-L</code> 跟隨重新導向；<code>--fail</code> 遇到 HTTP 錯誤回結束碼 22；<code>-s</code> 安靜模式。</li>
  </ul>
  <p class="req">完整參數對照見第 6 節；想用瀏覽器操作，見第 7 節的 mycurl2 網頁加值。</p>

  <h2 id="quick">5 · 快速開始（首次操作流程）</h2>
  <p>第一次用，跟著這五步走：</p>
  <ol class="steps">
    <li><b>開啟終端機</b>，切換到這個專案的根目錄（能看到 <code>homework/</code> 的那層）。</li>
    <li><b>確認 Python</b>：執行下面這行，有印出 <code>Python 3.8</code> 以上就算過關。
      <div class="cmd">python --version<button onclick="copy(this)">複製</button></div></li>
    <li><b>跑第一個請求</b>：複製執行下面這行，看到一堆 HTML 印出來就是成功。
      <div class="cmd">python homework/HW1/mycurl/mycurl.py https://example.com<button onclick="copy(this)">複製</button></div></li>
    <li><b>加上選項玩玩看</b>：<code>-v</code> 看來往過程，<code>-i</code> 看回應標頭。
      <div class="cmd">python homework/HW1/mycurl/mycurl.py -v https://httpbin.org/get<button onclick="copy(this)">複製</button></div></li>
    <li><b>存成檔案或網頁</b>：<code>-o</code> 存 body；想看排版過的就用 mycurl2。
      <div class="cmd">python homework/HW1/mycurl/mycurl.py -H "X-Token: abc" -i -o out.json https://httpbin.org/get<button onclick="copy(this)">複製</button></div>
      <div class="cmd">python homework/HW1/mycurl/mycurl2.py -i https://example.com --html-out report.html<button onclick="copy(this)">複製</button></div></li>
  </ol>
  <p class="req">想跑完整驗證（含 13 個單元測試）：</p>
  <div class="cmd">python -m unittest discover -s homework/HW1/mycurl/tests -v<button onclick="copy(this)">複製</button></div>

  <h2 id="compare">6 · curl 對照表</h2>
  <table>
    <tr><th>curl</th><th>mycurl / mycurl2</th><th>說明</th></tr>
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

  <h2 id="web">7 · mycurl2 多了什麼（超集加值）</h2>
  <ol class="tight">
    <li><code>--html-out FILE</code>：請求照常用 mycurl 核心發送，回應額外包裝成排版過的 HTML 報告（狀態、請求/回應標頭、內容預覽），雙擊用瀏覽器開。</li>
    <li><code>--serve [PORT]</code>：啟動本機網頁操作介面（只聽 127.0.0.1），瀏覽器填 URL/方法/標頭/資料，後端發送後結果直接顯示成網頁。</li>
    <li><code>--demo-out FILE</code>：產生本介紹頁。因為核心是 import 自 mycurl.py，行為保證與 mycurl 一致。</li>
  </ol>

  <h2>8 · 實作重點（報告可寫）</h2>
  <ol class="tight">
    <li>自訂 <code>NoRedirect(HTTPRedirectHandler)</code> 擋掉自動導向，自己依 <code>-L</code> 手動跟，<code>-v</code> 才能印出每一站的 <code>&gt;</code> / <code>&lt;</code>。</li>
    <li><code>HTTPError</code> 照常回傳 status + body，只有加 <code>--fail</code> 才回結束碼 22。</li>
    <li>body 用 <code>sys.stdout.buffer</code> 寫 bytes（圖片/二進位不爛掉）；<code>-v</code> 全走 stderr，不污染 pipe / 存檔。</li>
    <li>mycurl2 的 parser 直接繼承 mycurl，請求核心直接呼叫 <code>do_request</code>，所以「功能一樣」是結構保證，不是口頭保證。</li>
  </ol>

  <h2>9 · 專案結構</h2>
  <div class="cmd">homework/HW1/mycurl/
  mycurl.py      # 主程式 (約 {nlines} 行, 核心)
  mycurl2.py     # 超集: import mycurl + --html-out/--serve/--demo-out
  index.html     # 本頁 (雙擊用瀏覽器開)
  tests/         # 13 個測試</div>

  <h2 id="src">10 · 完整原始碼（mycurl.py）</h2>
  <details open>
    <summary>點我展開 / 收合 · 共 {nlines} 行</summary>
    <pre class="src"><code>{esc}</code></pre>
  </details>

  <h2 id="test">11 · test.sh 測試結果</h2>
  <p>一鍵檢測 <code>bash homework/HW1/mycurl/test.sh</code> 的最新結果：<b>{summary}</b>（含 mycurl / mycurl2 基本指令、13 個單元測試、實機請求、兩支輸出一致性、--html-out、--serve）。完整過程：</p>
  <details>
    <summary>點我展開完整檢測紀錄</summary>
    <pre class="src"><code>{report_esc}</code></pre>
  </details>

  <div class="foot">mycurl / mycurl2 · HW1 · 類似 curl 的專案程式 · Python 標準函式庫 only</div>
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


def _write_demo(args) -> int:
    src_path = pathlib.Path(args.source)
    if not src_path.is_file():
        print(f"mycurl2: 找不到原始碼: {src_path}", file=sys.stderr)
        return 2
    try:
        code = src_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"mycurl2: 讀取失敗: {e}", file=sys.stderr)
        return 23
    out = pathlib.Path(args.demo_out)
    if not out.is_absolute():
        out = pathlib.Path(__file__).with_name(out.name)
    rep_path = pathlib.Path(__file__).with_name("test-report.txt")
    report = ""
    if rep_path.is_file():
        raw = rep_path.read_bytes()
        for enc in ("utf-8", "cp950", "big5"):
            try:
                report = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            report = raw.decode("utf-8", errors="replace")
    try:
        out.write_text(build_showcase_html(code, args.title, report), encoding="utf-8")
    except OSError as e:
        print(f"mycurl2: 寫入失敗: {e}", file=sys.stderr)
        return 23
    print(f"已產生 {out} (內嵌 {len(code.splitlines())} 行原始碼)")
    return 0


# ---------------------------------------------------------------- 主流程 (與 mycurl.main 相同邏輯)

def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(VERSION)
        return 0
    if args.serve is not None:
        return run_serve(args.serve)
    if args.demo_out is not None and not args.url:
        return _write_demo(args)
    if args.demo_out is not None and args.url:
        print("mycurl2: 警告: 同時給 URL 與 --demo-out, 只執行請求 (忽略 --demo-out)",
              file=sys.stderr)

    if not args.url:
        parser.print_usage(sys.stderr)
        print("mycurl2: 需要提供 URL (例: mycurl2 https://example.com)",
              file=sys.stderr)
        return 2
    if not args.url.startswith(("http://", "https://")):
        if not args.silent:
            print(f"mycurl2: 不支援的 URL (只支援 http/https): {args.url}",
                  file=sys.stderr)
        return 2

    # 方法 (以下與 mycurl.main 相同流程, 共用同一批函式)
    try:
        body, is_json = load_data(args.data, args.json_data)
    except FileNotFoundError as e:
        if not args.silent:
            print(f"mycurl2: 讀取資料檔失敗: {e}", file=sys.stderr)
        return 26
    except OSError as e:
        if not args.silent:
            print(f"mycurl2: 讀取資料失敗: {e}", file=sys.stderr)
        return 26

    method = args.method or ("POST" if body is not None else "GET")
    method = method.upper()

    # 標頭
    headers = []
    try:
        for h in args.header:
            headers.append(parse_header(h))
    except ValueError as e:
        if not args.silent:
            print(f"mycurl2: {e}", file=sys.stderr)
        return 2
    header_keys = {k.lower() for k, _ in headers}
    if "user-agent" not in header_keys:
        headers.append(("User-Agent", args.user_agent))
    if body is not None and "content-type" not in header_keys:
        headers.append(("Content-Type",
                        "application/json" if is_json else "application/x-www-form-urlencoded"))
    if args.user:
        if ":" not in args.user:
            if not args.silent:
                print("mycurl2: -u 格式為 user:pass", file=sys.stderr)
            return 2
        import base64
        token = base64.b64encode(args.user.encode()).decode()
        headers.append(("Authorization", f"Basic {token}"))
    if body is not None and "content-length" not in header_keys:
        headers.append(("Content-Length", str(len(body))))

    ssl_context = make_ssl_context(args.insecure)

    try:
        status, resp_headers, data, final_url = do_request(
            args.url, method, headers, body, args.timeout, ssl_context,
            args.location, args.max_redirs, args.verbose)
    except urllib.error.URLError as e:
        if not args.silent:
            print(f"mycurl2: 連線失敗: {e.reason}", file=sys.stderr)
        return 7
    except TimeoutError:
        if not args.silent:
            print("mycurl2: 請求逾時", file=sys.stderr)
        return 28
    except OSError as e:
        if not args.silent:
            print(f"mycurl2: 請求失敗: {e}", file=sys.stderr)
        return 7

    is_error = status >= 400
    if args.fail and is_error:
        if not args.silent:
            print(f"mycurl2: HTTP {status} (使用 --fail, 不輸出 body)", file=sys.stderr)
        return 22

    out_path = resolve_output_path(args.output, args.remote_name, final_url)

    # 組合輸出 (含 -i 標頭) —— 與 mycurl 相同
    head = b""
    if args.include:
        status_line = f"HTTP/1.1 {status}\r\n".encode("latin-1")
        hdr_lines = "".join(f"{k}: {v}\r\n" for k, v in resp_headers).encode("latin-1")
        head = status_line + hdr_lines + b"\r\n"

    try:
        if out_path:
            with open(out_path, "wb") as f:
                f.write(head + data)
            if args.verbose:
                print(f"* 已儲存 {len(data)} bytes 到 {out_path}", file=sys.stderr)
        else:
            sys.stdout.buffer.write(head + data)
            sys.stdout.buffer.flush()
        if args.html_out:
            report = build_report_html(args.url, method, headers, status,
                                       resp_headers, data, final_url)
            with open(args.html_out, "w", encoding="utf-8") as f:
                f.write(report)
            if args.verbose:
                print(f"* 已產生 HTML 報告 {args.html_out}", file=sys.stderr)
    except BrokenPipeError:
        return 0
    except OSError as e:
        if not args.silent:
            print(f"mycurl2: 寫入輸出失敗: {e}", file=sys.stderr)
        return 23

    return 22 if is_error else 0


if __name__ == "__main__":
    sys.exit(main())
