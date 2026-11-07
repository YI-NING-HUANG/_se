from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .archive_api import ARCHIVE_BASE, ArchiveAPI, parse_forum_id, parse_thread_id
from .build import Builder
from .db import Store
from .download import Downloader
from .live import LiveForum
from .net import HttpClient, RobotsDenied
from .util import DEFAULT_DELAY, DEFAULT_RETRIES, DEFAULT_TIMEOUT, USER_AGENT, human_size, utc_now

ANNOUNCEMENTS = ["199"]
PLUGIN_FORUMS = [
    "135", "184", "137", "128", "36", "35", "37", "39", "40", "47", "34", "129",
    "165", "136", "127", "102",
]
RESOURCE_FORUMS = [
    "28", "29", "30", "131", "185", "110", "112", "116", "117", "118", "133",
    "179", "160", "149", "115", "51", "49", "101", "70", "73", "154", "22", "23",
    "24", "25", "130", "182", "191", "164", "174", "175", "1000000003",
]
PRESETS = {
    "announcements": ANNOUNCEMENTS,
    "plugins": PLUGIN_FORUMS,
    "resources": RESOURCE_FORUMS,
    "assets": list(dict.fromkeys(PLUGIN_FORUMS + RESOURCE_FORUMS + ANNOUNCEMENTS)),
    "everything": None,
}


def _log(verbose: int, level: int = 0):
    def inner(message: str, msg_level: int = 0) -> None:
        if verbose >= max(level, msg_level):
            print(message, flush=True)
    return inner


def make_client(args) -> HttpClient:
    return HttpClient(
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        user_agent=args.user_agent,
        robots=args.robots,
        log=lambda msg: print(msg, file=sys.stderr, flush=True),
    )


def cmd_init(args) -> int:
    with Store(args.out) as store:
        if not store.get_meta("created_at"):
            store.set_meta("created_at", utc_now())
        print(f"initialized archive at {store.root}")
        print(f"database: {store.db_path}")
    return 0


def cmd_list_forums(args) -> int:
    with Store(args.out) as store:
        forums = store.forums()
        if not forums or args.refresh:
            client = make_client(args)
            api = ArchiveAPI(client, base=args.archive_base, root=store.root, save_raw=False)
            forums_data = api.forums()
            store.upsert_forums(forums_data)
            forums = store.forums()
        if args.json:
            print(json.dumps([dict(f) for f in forums], ensure_ascii=False, indent=2))
        else:
            for forum in forums:
                print(f"{forum['forum_id']:>10}  {forum['title'] or ''}")
    return 0


def cmd_discover(args) -> int:
    log = _log(args.verbose)
    with Store(args.out) as store:
        client = make_client(args)
        if args.source == "archive":
            api = ArchiveAPI(
                client, base=args.archive_base, root=store.root, save_raw=not args.no_raw
            )
            scopes_threads = [parse_thread_id(t) for t in (args.thread or [])]
            scopes_forums = list(dict.fromkeys(
                parse_forum_id(f) for f in (args.forum or [])
            ))
            if args.preset:
                preset = PRESETS.get(args.preset)
                if preset is None:
                    scopes_forums = []
                    args.all_forums = True
                else:
                    scopes_forums = list(dict.fromkeys(scopes_forums + preset))
            if not scopes_threads and not scopes_forums and not args.all_forums:
                print("nothing selected: use --thread, --forum, --preset, or --all-forums", file=sys.stderr)
                return 2
            store.set_meta("source", args.source)
            store.set_meta(
                "scope",
                json.dumps({
                    "threads": scopes_threads,
                    "forums": scopes_forums,
                    "all_forums": bool(args.all_forums),
                    "preset": args.preset,
                }, ensure_ascii=False),
            )
            for tid in scopes_threads:
                log(f"discovering thread {tid}", 0)
                result = api.discover_thread(store, tid, max_pages=args.max_pages)
                print(
                    f"thread {result['thread_id']}: {result['posts']} posts, "
                    f"{result['pages']} pages :: {result.get('title') or ''}"
                )
            if args.all_forums:
                print("discovering all forums (this can run for a long time; Ctrl+C is safe)")
                result = api.discover_all(
                    store, with_posts=args.with_posts, max_threads=args.max_threads,
                    max_pages_per_thread=args.max_pages, progress=log,
                )
                print(
                    f"forums: {result['forums']}, threads seen: {result['threads']}, "
                    f"posts stored: {result['posts']}"
                )
            else:
                for fid in scopes_forums:
                    log(f"discovering forum {fid}", 0)
                    result = api.discover_forum(
                        store, fid, with_posts=args.with_posts,
                        max_threads=args.max_threads,
                        max_pages_per_thread=args.max_pages,
                        progress=log,
                    )
                    print(
                        f"forum {result['forum_id']}: {result['threads']} threads seen, "
                        f"{result['posts']} posts stored"
                    )
            counts = store.counts()
            print(
                f"archive now: {counts['threads']} threads, {counts['posts']} posts, "
                f"{counts['assets']} asset refs"
            )
        else:
            live = LiveForum(client, store.root)
            store.set_meta("source", "live")
            store.set_meta(
                "scope",
                json.dumps({"threads": args.thread or [], "forums": args.forum or []}, ensure_ascii=False),
            )
            if not args.thread and not args.forum:
                print("live mode needs --thread URL or --forum URL", file=sys.stderr)
                return 2
            for thread_url in args.thread or []:
                try:
                    result = live.discover_thread_url(
                        store, thread_url, max_pages=args.max_pages, force=args.force,
                        save_raw=not args.no_raw,
                    )
                except RobotsDenied as exc:
                    print(f"blocked by robots.txt: {exc}\n"
                          "Use --robots warn (or ignore) only if you have permission.",
                          file=sys.stderr)
                    return 3
                print(
                    f"thread {result['thread_id']}: {result['posts']} posts, "
                    f"{result['pages']} pages :: {result.get('title') or ''}"
                )
            for forum_url in args.forum or []:
                try:
                    result = live.discover_forum_url(
                        store, forum_url, with_posts=args.with_posts,
                        max_pages=args.max_pages, max_threads=args.max_threads,
                        save_raw=not args.no_raw,
                    )
                except RobotsDenied as exc:
                    print(f"blocked by robots.txt: {exc}\n"
                          "Use --robots warn (or ignore) only if you have permission.",
                          file=sys.stderr)
                    return 3
                print(
                    f"forum {result['forum_id']}: {result['threads']} threads seen, "
                    f"{result['posts']} posts stored"
                )
    return 0


def cmd_download(args) -> int:
    with Store(args.out) as store:
        client = make_client(args)
        downloader = Downloader(
            store, client, store.root,
            max_bytes=int(args.max_mb * 1024 * 1024),
            log=lambda msg: print(msg, flush=True),
        )
        try:
            result = downloader.run(
                kinds=args.kind or None,
                limit=args.limit,
                hosts=args.host or None,
                dry_run=args.dry_run,
                retry_errors=args.retry_errors,
            )
        except RobotsDenied as exc:
            print(f"blocked by robots.txt: {exc}\n"
                  "Use --robots warn (or ignore) only if you have permission.", file=sys.stderr)
            return 3
        print(
            f"downloaded {result['downloaded']}, failed {result['failed']}, "
            f"skipped {result['skipped']}, blocked {result['blocked']}, "
            f"bytes {human_size(result['bytes'])}"
        )
        if result["blocked"] and not result["downloaded"]:
            print(
                "nothing downloaded because robots.txt disallowed the selected URLs; "
                "use --robots warn (or ignore) only if you have permission.",
                file=sys.stderr,
            )
            return 3
    return 0


def cmd_build(args) -> int:
    with Store(args.out) as store:
        builder = Builder(store, store.root, search_index=not args.no_search,
                          log=lambda msg: print(msg, flush=True))
        counts = builder.build()
        print(f"offline site: {store.root / 'site' / 'index.html'}")
        print(
            f"threads {counts['threads']}, posts {counts['posts']}, "
            f"files saved {counts['assets_done']}/{counts['assets']}"
        )
    return 0


def cmd_status(args) -> int:
    with Store(args.out) as store:
        counts = store.counts()
        if args.json:
            print(json.dumps(counts, indent=2))
        else:
            for key, value in counts.items():
                if key == "asset_bytes":
                    print(f"{key:>18}: {human_size(value)}")
                else:
                    print(f"{key:>18}: {value}")
        errors = store.conn.execute(
            "SELECT url, kind, http_status, error FROM assets WHERE status='error' "
            "ORDER BY priority LIMIT 10"
        ).fetchall()
        if errors and not args.json:
            print("\nfirst errors:")
            for row in errors:
                print(f"  [{row['kind']}] {row['url']} :: {row['error']}")
    return 0


def cmd_verify(args) -> int:
    with Store(args.out) as store:
        client = make_client(args)
        downloader = Downloader(store, client, store.root)
        result = downloader.verify(fix=args.fix)
        print(
            f"checked {result['checked']} files; missing {len(result['missing'])}, "
            f"corrupt {len(result['bad'])}"
        )
        for url in (result["missing"] + result["bad"])[:20]:
            print(f"  {url}")
        return 1 if result["missing"] or result["bad"] else 0


def cmd_export(args) -> int:
    with Store(args.out) as store:
        out = Path(args.output) if args.output else store.root / "exports" / (
            f"{args.what}.jsonl" if args.format == "jsonl" else f"{args.what}.csv"
        )
        if args.format == "csv":
            if args.what != "assets":
                print("CSV export is only implemented for --what assets", file=sys.stderr)
                return 2
            n = store.export_assets_csv(out)
        else:
            n = store.export_jsonl(out, args.what)
        print(f"wrote {n} rows to {out}")
    return 0


def add_common(p: argparse.ArgumentParser, defaults: bool = True) -> None:
    def d(value):
        return value if defaults else argparse.SUPPRESS

    p.add_argument("--out", default=d("archive"),
                   help="archive directory (default: ./archive)")
    p.add_argument("--delay", type=float, default=d(DEFAULT_DELAY),
                   help="seconds between requests to the same host (default: 1.0)")
    p.add_argument("--timeout", type=float, default=d(DEFAULT_TIMEOUT))
    p.add_argument("--retries", type=int, default=d(DEFAULT_RETRIES))
    p.add_argument("--user-agent", default=d(USER_AGENT))
    p.add_argument("--robots", choices=["respect", "warn", "ignore"], default=d("respect"),
                   help="robots.txt policy for live requests (default: respect)")
    p.add_argument("-v", "--verbose", action="count", default=d(0))
    p.add_argument("--archive-base", default=d(ARCHIVE_BASE),
                   help="base URL of the community archive JSON API")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xfrescue",
        description="Polite, resumable preservation of XenForo forums (built for RPG Maker Web).",
    )
    add_common(parser, defaults=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create the archive database")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("list-forums", help="list forums known to the archive")
    p.add_argument("--refresh", action="store_true", help="fetch the forum list again")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list_forums)

    p = sub.add_parser("discover", help="discover threads/posts and record asset URLs")
    p.add_argument("--source", choices=["archive", "live"], default="archive",
                   help="archive: community JSON API; live: forums.rpgmakerweb.com HTML")
    p.add_argument("--thread", action="append", help="thread id or URL (repeatable)")
    p.add_argument("--forum", action="append", help="forum id or URL (repeatable)")
    p.add_argument("--all-forums", action="store_true")
    p.add_argument("--preset", choices=sorted(PRESETS), help="curated forum selection")
    p.add_argument("--with-posts", action="store_true",
                   help="also fetch every post in selected forums (needed to find files)")
    p.add_argument("--max-threads", type=int, default=None)
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--force", action="store_true", help="live mode: refetch even if complete")
    p.add_argument("--no-raw", action="store_true", help="do not save raw JSON/HTML")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("download", help="download pending assets")
    p.add_argument("--kind", action="append",
                   help="only these kinds: attachment,image,archive,code,document,audio,video,page_asset")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--host", action="append", help="only these hosts")
    p.add_argument("--max-mb", type=float, default=200.0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--retry-errors", action="store_true")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("build", help="build the offline HTML site")
    p.add_argument("--no-search", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("status", help="show archive counts")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("verify", help="verify downloaded file hashes")
    p.add_argument("--fix", action="store_true", help="mark missing/corrupt files as pending")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("export", help="export database rows")
    p.add_argument("--what", choices=["forums", "threads", "posts", "assets"], required=True)
    p.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    p.add_argument("--output", default=None)
    p.set_defaults(func=cmd_export)

    for command_parser in sub.choices.values():
        add_common(command_parser, defaults=False)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\ninterrupted; progress is saved, run the same command to resume.", file=sys.stderr)
        return 130
    except RobotsDenied as exc:
        print(f"blocked by robots.txt: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
