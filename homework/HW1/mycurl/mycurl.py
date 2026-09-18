#!/usr/bin/env python3
"""mycurl - 類似 curl 的最小可用版 HTTP 客戶端 (只用 Python 標準函式庫).

功能:
  GET / POST / 任意 -X 方法, -H 自訂標頭, -d 傳送資料, --json 快捷,
  -o 存檔, -O 用遠端檔名存檔, -i 顯示回應標頭, -v 顯示請求/回應過程,
  -L 跟隨重新導向, --timeout, -u Basic 認證, -A User-Agent,
  -k 略過 SSL 驗證, --fail 讓 HTTP 錯誤回非零結束碼.

用法範例:
  python mycurl/mycurl.py https://example.com
  python mycurl/mycurl.py -v https://httpbin.org/get
  python mycurl/mycurl.py -H "X-Token: abc" -d "a=1&b=2" https://httpbin.org/post
  python mycurl/mycurl.py -o out.html https://example.com
"""

import argparse
import base64
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


VERSION = "mycurl 0.1.0 (python stdlib only)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mycurl",
        description="類似 curl 的最小可用版 HTTP 客戶端 (Python 標準函式庫實作)",
    )
    p.add_argument("url", nargs="?", help="要請求的 URL, 例: https://example.com")
    p.add_argument("-X", "--request", dest="method", default=None,
                   help="HTTP 方法, 例: GET, POST, PUT, DELETE (預設: 有 -d 則為 POST, 否則 GET)")
    p.add_argument("-H", "--header", action="append", default=[],
                   metavar='"Key: Value"', help="自訂請求標頭, 可重複使用")
    p.add_argument("-d", "--data", action="append", default=[],
                   metavar="DATA", help="請求 body. 多個 -d 會用 & 連接. @file 表示從檔案讀取")
    p.add_argument("--json", dest="json_data", default=None,
                   metavar="JSON", help="傳送 JSON, 自動加上 Content-Type: application/json")
    p.add_argument("-o", "--output", default=None, help="把回應 body 存到檔案 (而非 stdout)")
    p.add_argument("-O", "--remote-name", action="store_true",
                   help="用 URL 最後一段檔名存檔 (類似 curl -O)")
    p.add_argument("-i", "--include", action="store_true", help="輸出包含回應標頭")
    p.add_argument("-v", "--verbose", action="store_true", help="顯示請求/回應標頭過程 (輸出到 stderr)")
    p.add_argument("-L", "--location", action="store_true", help="跟隨 3xx 重新導向")
    p.add_argument("--max-redirs", type=int, default=5, help="最多跟隨幾次導向 (預設 5, 需搭配 -L)")
    p.add_argument("--timeout", type=float, default=30, help="逾時秒數 (預設 30)")
    p.add_argument("-u", "--user", default=None, metavar="user:pass", help="HTTP Basic 認證")
    p.add_argument("-A", "--user-agent", default="mycurl/0.1.0",
                   help="自訂 User-Agent (預設 mycurl/0.1.0)")
    p.add_argument("-k", "--insecure", action="store_true", help="略過 SSL 憑證驗證 (測試用)")
    p.add_argument("--fail", action="store_true",
                   help="HTTP >= 400 時結束碼為 22 且不在 stdout 輸出 body (類似 curl -f)")
    p.add_argument("-s", "--silent", action="store_true", help="安靜模式: 不輸出錯誤訊息")
    p.add_argument("--version", action="store_true", help="顯示版本")
    return p


def parse_header(raw: str):
    """解析 'Key: Value' -> (Key, Value). 沒有冒號則報錯."""
    if ":" not in raw:
        raise ValueError(f"標頭格式錯誤 (需要 'Key: Value'): {raw!r}")
    key, value = raw.split(":", 1)
    key, value = key.strip(), value.strip()
    if not key:
        raise ValueError(f"標頭名稱不可為空: {raw!r}")
    return key, value


def load_data(data_list, json_data):
    """回傳 (body_bytes_or_None, is_json)."""
    if json_data is not None:
        return json_data.encode("utf-8"), True
    if not data_list:
        return None, False
    parts = []
    for item in data_list:
        if item.startswith("@"):
            path = item[1:]
            with open(path, "rb") as f:
                parts.append(f.read().decode("utf-8"))
        else:
            parts.append(item)
    return ("&".join(parts)).encode("utf-8"), False


def make_ssl_context(insecure: bool):
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """擋下自動導向, 讓我們自己依 -L 決定要不要跟隨 (方便 -v 顯示每次過程)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def do_request(url, method, headers, body, timeout, ssl_context,
               follow_redirects, max_redirs, verbose):
    """發送請求, 回傳 (status, resp_headers_list, body_bytes, final_url).

    遇到 3xx 且 follow_redirects=True 時手動跟隨, 以便 -v 能印出每一站.
    """
    opener = urllib.request.build_opener(NoRedirect)
    current_url = url
    redirects = 0

    while True:
        req = urllib.request.Request(current_url, data=body, method=method)
        for k, v in headers:
            req.add_header(k, v)

        if verbose:
            parsed = urllib.parse.urlparse(current_url)
            print(f"> {method} {parsed.path or '/'}" +
                  (f"?{parsed.query}" if parsed.query else "") +
                  " HTTP/1.1", file=sys.stderr)
            print(f"> Host: {parsed.netloc}", file=sys.stderr)
            for k, v in headers:
                print(f"> {k}: {v}", file=sys.stderr)
            print(">", file=sys.stderr)

        try:
            kwargs = {"timeout": timeout}
            if ssl_context is not None:
                kwargs["context"] = ssl_context
            with opener.open(req, **kwargs) as resp:
                status = resp.status
                resp_headers = list(resp.getheaders())
                data = resp.read()
                final_url = resp.geturl()
                if verbose:
                    print(f"< HTTP/1.1 {status} {resp.reason}", file=sys.stderr)
                    for k, v in resp_headers:
                        print(f"< {k}: {v}", file=sys.stderr)
                    print("<", file=sys.stderr)
                return status, resp_headers, data, final_url
        except urllib.error.HTTPError as e:
            # 3xx: urllib 會先丟 HTTPError (因為我們擋下自動導向)
            if e.code in (301, 302, 303, 307, 308):
                if verbose:
                    print(f"< HTTP/1.1 {e.code} {e.reason}", file=sys.stderr)
                    for k, v in (e.headers.items() if e.headers else []):
                        print(f"< {k}: {v}", file=sys.stderr)
                    print("<", file=sys.stderr)
                if follow_redirects and redirects < max_redirs:
                    loc = e.headers.get("Location") if e.headers else None
                    if not loc:
                        raise
                    current_url = urllib.parse.urljoin(current_url, loc)
                    redirects += 1
                    # 303 一律轉 GET; 301/302 若原方法是 POST 也轉 GET (同 curl 預設行為)
                    if e.code == 303 or (e.code in (301, 302) and method == "POST"):
                        method = "GET"
                        body = None
                    if verbose:
                        print(f"* 跟隨重新導向 ({redirects}): {current_url}", file=sys.stderr)
                    continue
                # 不跟隨: 把 3xx 當正常回應回傳
                resp_headers = list(e.headers.items()) if e.headers else []
                try:
                    data = e.read()
                except Exception:
                    data = b""
                return e.code, resp_headers, data, current_url
            # 4xx/5xx: 照常回傳 status + body, 由呼叫端依 --fail 決定結束碼
            resp_headers = list(e.headers.items()) if e.headers else []
            try:
                data = e.read()
            except Exception:
                data = b""
            if verbose:
                print(f"< HTTP/1.1 {e.code} {e.reason}", file=sys.stderr)
                for k, v in resp_headers:
                    print(f"< {k}: {v}", file=sys.stderr)
                print("<", file=sys.stderr)
            return e.code, resp_headers, data, current_url


def resolve_output_path(output, remote_name, url):
    if output:
        return output
    if remote_name:
        path = urllib.parse.urlparse(url).path.rstrip("/")
        name = os.path.basename(path) or "index.html"
        return name
    return None


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(VERSION)
        return 0
    if not args.url:
        parser.print_usage(sys.stderr)
        print("mycurl: 需要提供 URL (例: mycurl https://example.com)", file=sys.stderr)
        return 2
    if not args.url.startswith(("http://", "https://")):
        if not args.silent:
            print(f"mycurl: 不支援的 URL (只支援 http/https): {args.url}", file=sys.stderr)
        return 2

    # 方法
    try:
        body, is_json = load_data(args.data, args.json_data)
    except FileNotFoundError as e:
        if not args.silent:
            print(f"mycurl: 讀取資料檔失敗: {e}", file=sys.stderr)
        return 26  # 對齊 curl 讀檔失敗結束碼
    except OSError as e:
        if not args.silent:
            print(f"mycurl: 讀取資料失敗: {e}", file=sys.stderr)
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
            print(f"mycurl: {e}", file=sys.stderr)
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
                print("mycurl: -u 格式為 user:pass", file=sys.stderr)
            return 2
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
            print(f"mycurl: 連線失敗: {e.reason}", file=sys.stderr)
        return 7  # 對齊 curl 連線失敗結束碼
    except TimeoutError:
        if not args.silent:
            print("mycurl: 請求逾時", file=sys.stderr)
        return 28
    except OSError as e:
        if not args.silent:
            print(f"mycurl: 請求失敗: {e}", file=sys.stderr)
        return 7

    is_error = status >= 400
    if args.fail and is_error:
        if not args.silent:
            print(f"mycurl: HTTP {status} (使用 --fail, 不輸出 body)", file=sys.stderr)
        return 22

    out_path = resolve_output_path(args.output, args.remote_name, final_url)

    # 組合輸出 (含 -i 標頭)
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
    except BrokenPipeError:
        return 0
    except OSError as e:
        if not args.silent:
            print(f"mycurl: 寫入輸出失敗: {e}", file=sys.stderr)
        return 23

    return 22 if is_error else 0


if __name__ == "__main__":
    sys.exit(main())
