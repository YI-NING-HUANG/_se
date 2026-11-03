from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .build import build_site, write_archive_readme
from .crawl import Crawler
from .download import Downloader, asset_kind_filter
from .net import HttpClient
from .policy import CrawlPolicy
from .store import Store
from .util import (
    DEFAULT_ASSET_LIMIT_MB,
    DEFAULT_DELAY,
    DEFAULT_PAGE_LIMIT_MB,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    USER_AGENT,
    human_size,
    normalize_url,
)
from .verify import verify_archive


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--out", default="forum-archive",
        help="封存資料夾（預設 forum-archive）",
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY,
        help="同一主機的請求間隔秒數（預設 1.0）",
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT,
        help=f"單一請求逾時秒數（預設 {DEFAULT_TIMEOUT:g}）",
    )
    parser.add_argument(
        "--retries", type=int, default=DEFAULT_RETRIES,
        help=f"失敗重試次數（預設 {DEFAULT_RETRIES}）",
    )
    parser.add_argument(
        "--user-agent", default=USER_AGENT,
        help="自訂 User-Agent",
    )
    parser.add_argument(
        "--robots", choices=("respect", "warn", "ignore"), default="respect",
        help="robots.txt 模式；預設 respect",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="顯示詳細進度")
    parser.add_argument("-q", "--quiet", action="store_true", help="只顯示錯誤")
    return parser


def _add_crawl_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--url", action="append", default=[],
        help="起始網址；可重複。已有種子時可省略",
    )
    parser.add_argument(
        "--allow-host", action="append", default=[],
        help="額外允許的網域（可含 *.example.com）",
    )
    parser.add_argument(
        "--path-prefix", action="append", default=[],
        help="只爬取此路徑前綴；可重複",
    )
    parser.add_argument(
        "--include", action="append", default=[],
        help="只納入符合 glob 的網址",
    )
    parser.add_argument(
        "--exclude", action="append", default=[],
        help="排除符合 glob 的網址；可重複",
    )
    parser.add_argument(
        "--no-default-excludes", action="store_true",
        help="停用登入、搜尋、管理等等預設排除規則",
    )
    parser.add_argument(
        "--external-assets", choices=("none", "same-host", "all"), default="same-host",
        help="外部素材範圍；預設只下載站內素材",
    )
    parser.add_argument("--max-pages", type=int, help="本次最多抓取幾頁")
    parser.add_argument("--max-depth", type=int, help="最大連結深度")
    parser.add_argument(
        "--page-mb", type=float, default=DEFAULT_PAGE_LIMIT_MB,
        help=f"單一 HTML 頁面上限 MB（預設 {DEFAULT_PAGE_LIMIT_MB:g}）",
    )
    parser.add_argument("--retry-errors", action="store_true", help="重試先前失敗的頁面")
    parser.add_argument("--force", action="store_true", help="重新抓取已完成頁面")


def _add_download_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--kind", default=None,
        help="只下載指定素材類型，逗號分隔（image,attachment,archive,...）",
    )
    parser.add_argument("--host", help="只下載指定主機的素材")
    parser.add_argument("--limit", type=int, help="本次最多處理幾個素材")
    parser.add_argument(
        "--asset-mb", type=float, default=DEFAULT_ASSET_LIMIT_MB,
        help=f"單一素材上限 MB（預設 {DEFAULT_ASSET_LIMIT_MB:g}）",
    )
    if "--retry-errors" not in parser._option_string_actions:
        parser.add_argument("--retry-errors", action="store_true", help="重試先前失敗的素材")
    parser.add_argument("--dry-run", action="store_true", help="只列出待下載素材")
    parser.add_argument("--no-css-deps", action="store_true", help="不從 CSS 探索字型與圖片")


def _add_build_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-banner", action="store_true", help="不插入 ForumKeep 離線橫幅")
    parser.add_argument("--keep-scripts", action="store_true", help="保留頁面 JavaScript（預設移除）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forumkeep",
        description="ForumKeep：公開唯讀論壇的禮貌、可續傳離線保存工具",
    )
    parser.add_argument("--version", action="version", version=f"ForumKeep {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    common = _common_parser()

    init = sub.add_parser(
        "init", parents=[common], help="建立封存並記錄起始網址"
    )
    init.add_argument("--url", action="append", required=True, help="起始網址；可重複")

    crawl = sub.add_parser(
        "crawl", parents=[common], help="沿站內連結抓取頁面並蒐集素材網址"
    )
    _add_crawl_options(crawl)

    download = sub.add_parser(
        "download", parents=[common], help="下載已蒐集但尚未取得的素材"
    )
    _add_download_options(download)

    build = sub.add_parser(
        "build", parents=[common], help="把封存建成可離線瀏覽的靜態網站"
    )
    _add_build_options(build)

    run = sub.add_parser(
        "run", parents=[common], help="一次執行 crawl、download、build"
    )
    _add_crawl_options(run)
    _add_download_options(run)
    _add_build_options(run)

    status = sub.add_parser(
        "status", parents=[common], help="顯示封存進度與錯誤"
    )
    status.add_argument("--json", action="store_true", help="輸出 JSON")

    verify = sub.add_parser(
        "verify", parents=[common], help="驗證原始頁面與素材的 SHA-256"
    )
    verify.add_argument("--fix", action="store_true", help="把損壞項目重新排入佇列")
    verify.add_argument("--json", action="store_true", help="輸出 JSON")

    export = sub.add_parser(
        "export", parents=[common], help="匯出 pages/assets/links 資料"
    )
    export.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    export.add_argument(
        "--what", choices=("all", "pages", "assets", "links"), default="all"
    )
    export.add_argument("--path", help="輸出檔案或資料夾（預設 exports/）")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.retries < 0:
        parser.error("--retries 不可小於 0")
    if args.delay < 0:
        parser.error("--delay 不可小於 0")
    if args.timeout <= 0:
        parser.error("--timeout 必須大於 0")
    logger = _make_logger(args)
    try:
        if args.command == "init":
            return _cmd_init(args, logger)
        if args.command == "crawl":
            return _cmd_crawl(args, logger)
        if args.command == "download":
            return _cmd_download(args, logger)
        if args.command == "build":
            return _cmd_build(args, logger)
        if args.command == "run":
            return _cmd_run(args, logger)
        if args.command == "status":
            return _cmd_status(args)
        if args.command == "verify":
            return _cmd_verify(args, logger)
        if args.command == "export":
            return _cmd_export(args, logger)
    except KeyboardInterrupt:
        print("已中斷。再次執行相同命令會從 SQLite 續傳。", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"錯誤：{error}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1
    parser.print_help()
    return 2


def _make_logger(args):
    def log(message: str) -> None:
        if not args.quiet:
            print(message, file=sys.stderr)

    return log


def _open_store(args) -> Store:
    store = Store(args.out)
    store.set_meta("tool_version", __version__)
    store.set_meta("last_out", str(Path(args.out).resolve()))
    return store


def _apply_seeds(store: Store, urls: list[str]) -> list[str]:
    added = []
    for raw in urls:
        normalized = normalize_url(raw)
        if not normalized:
            raise ValueError(f"無效網址：{raw}")
        store.add_seed(normalized)
        added.append(normalized)
    seeds = store.seeds()
    if not seeds:
        raise ValueError("尚未設定起始網址，請加上 --url")
    return seeds


def _policy(args, seeds: list[str]) -> CrawlPolicy:
    allowed = list(getattr(args, "allow_host", []) or [])
    seed_hosts = []
    import urllib.parse

    for seed in seeds:
        host = (urllib.parse.urlsplit(seed).hostname or "").lower()
        if host and host not in seed_hosts:
            seed_hosts.append(host)
    allowed = seed_hosts + [host for host in allowed if host not in seed_hosts]
    return CrawlPolicy(
        seeds=seeds,
        allowed_hosts=allowed,
        path_prefixes=list(getattr(args, "path_prefix", []) or []),
        include_patterns=list(getattr(args, "include", []) or []),
        exclude_patterns=list(getattr(args, "exclude", []) or []),
        external_assets=getattr(args, "external_assets", "same-host"),
        max_depth=getattr(args, "max_depth", None),
        use_default_excludes=not getattr(args, "no_default_excludes", False),
    )


def _client(args, logger) -> HttpClient:
    return HttpClient(
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        user_agent=args.user_agent,
        robots=args.robots,
        max_page_bytes=int(getattr(args, "page_mb", DEFAULT_PAGE_LIMIT_MB) * 1024 * 1024),
        log=logger,
    )


def _cmd_init(args, logger) -> int:
    store = _open_store(args)
    try:
        seeds = _apply_seeds(store, args.url)
        write_archive_readme(store)
        logger(f"封存已建立：{store.root}")
        for seed in seeds:
            logger(f"  起始網址：{seed}")
        return 0
    finally:
        store.close()


def _run_crawl(args, store: Store, logger) -> dict:
    seeds = _apply_seeds(store, getattr(args, "url", []) or [])
    policy = _policy(args, seeds)
    client = _client(args, logger)
    crawler = Crawler(store, client, policy, log=logger, verbose=args.verbose)
    for seed in seeds:
        crawler.add_seed(seed)
    summary = crawler.run(
        max_pages=getattr(args, "max_pages", None),
        retry_errors=getattr(args, "retry_errors", False),
        force=getattr(args, "force", False),
    )
    logger(
        f"crawl 完成：{summary['fetched']} 頁、{summary['assets_found']} 個新素材、"
        f"{summary['errors']} 個錯誤、{summary.get('blocked', 0)} 個被 robots 阻擋"
    )
    return summary


def _cmd_crawl(args, logger) -> int:
    store = _open_store(args)
    try:
        _run_crawl(args, store, logger)
        write_archive_readme(store)
    finally:
        store.close()
    return 0


def _run_download(args, store: Store, logger) -> dict:
    seeds = store.seeds()
    if not seeds:
        raise ValueError("尚未設定起始網址，請先執行 init 或 crawl --url")
    policy = _policy(args, seeds)
    client = _client(args, logger)
    downloader = Downloader(store, client, policy, log=logger, verbose=args.verbose)
    kinds = asset_kind_filter(getattr(args, "kind", None))
    summary = downloader.run(
        kinds=kinds,
        host=getattr(args, "host", None),
        limit=getattr(args, "limit", None),
        retry_errors=getattr(args, "retry_errors", False),
        max_bytes=int(getattr(args, "asset_mb", DEFAULT_ASSET_LIMIT_MB) * 1024 * 1024),
        dry_run=getattr(args, "dry_run", False),
        mirror_css=not getattr(args, "no_css_deps", False),
    )
    if summary.get("dry_run"):
        logger(f"待下載素材：{summary['candidates']}")
    else:
        logger(
            f"download 完成：{summary['downloaded']} 個成功、"
            f"{summary['failed']} 個失敗、{summary['skipped']} 個略過、"
            f"{human_size(summary['bytes'])}"
        )
    return summary


def _cmd_download(args, logger) -> int:
    store = _open_store(args)
    try:
        _run_download(args, store, logger)
    finally:
        store.close()
    return 0


def _cmd_build(args, logger) -> int:
    store = _open_store(args)
    try:
        if not store.seeds():
            raise ValueError("封存內沒有起始網址，請先執行 crawl")
        build_site(
            store,
            banner=not args.no_banner,
            strip_scripts=not args.keep_scripts,
            log=logger,
        )
        write_archive_readme(store)
        logger("開啟 " + str((store.root / "site" / "index.html").resolve()))
    finally:
        store.close()
    return 0


def _cmd_run(args, logger) -> int:
    store = _open_store(args)
    try:
        _run_crawl(args, store, logger)
        _run_download(args, store, logger)
        build_site(
            store,
            banner=not args.no_banner,
            strip_scripts=not args.keep_scripts,
            log=logger,
        )
        write_archive_readme(store)
        logger("完成。開啟 " + str((store.root / "site" / "index.html").resolve()))
    finally:
        store.close()
    return 0


def _cmd_status(args) -> int:
    store = _open_store(args)
    try:
        counts = store.counts()
        errors = [dict(row) for row in store.errors(limit=50)]
        if args.json:
            print(json.dumps(
                {
                    "out": str(store.root.resolve()),
                    "seeds": store.seeds(),
                    "counts": counts,
                    "errors": errors,
                },
                ensure_ascii=False,
                indent=2,
            ))
            return 0
        print(f"封存：{store.root.resolve()}")
        print("來源：")
        for seed in store.seeds():
            print(f"  - {seed}")
        print("數量：")
        print(f"  頁面        {counts.get('pages', 0)}")
        print(f"  素材        {counts.get('assets', 0)}（{human_size(counts.get('asset_bytes', 0))}）")
        print(f"  連結        {counts.get('links', 0)}")
        queue = store.queue_counts()
        for status in ("pending", "working", "done", "error", "blocked", "skipped"):
            if queue.get(status):
                print(f"  佇列 {status:<8} {queue[status]}")
        if errors:
            print("最近錯誤/阻擋：")
            for row in errors:
                print(f"  [{row['type']}] {row['url']}")
                print(f"      {row['error']}")
        else:
            print("最近錯誤/阻擋：無")
        return 0
    finally:
        store.close()


def _cmd_verify(args, logger) -> int:
    store = _open_store(args)
    try:
        summary = verify_archive(store, fix=args.fix, log=logger)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(
                f"驗證：{summary['checked_pages']} 頁、{summary['checked_assets']} 個素材；"
                f"頁面問題 {len(summary['page_issues'])}、素材問題 {len(summary['asset_issues'])}"
            )
            if summary["fixed"]:
                print("損壞項目已重新排入佇列。")
        return 0 if summary["ok"] else 1
    finally:
        store.close()


def _cmd_export(args, logger) -> int:
    store = _open_store(args)
    try:
        exports = store.root / "exports"
        if args.format == "jsonl":
            path = Path(args.path) if args.path else exports / "archive.jsonl"
            count = store.export_jsonl(path, what=args.what)
        else:
            directory = Path(args.path) if args.path else exports
            count = store.export_csv(directory, what=args.what)
        logger(f"已匯出 {count} 筆資料")
        return 0
    finally:
        store.close()
