from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable

from .store import Store
from .util import human_size, sha256_file


def verify_archive(
    store: Store,
    *,
    fix: bool = False,
    log: Callable[[str], None] | None = None,
) -> dict:
    log = log or (lambda message: None)
    checked_pages = 0
    checked_assets = 0
    page_issues: list[dict] = []
    asset_issues: list[dict] = []
    for page in store.iter_pages():
        if page["status"] != "done":
            continue
        checked_pages += 1
        if not page["raw_path"]:
            page_issues.append({"url": page["url"], "error": "missing raw_path"})
            continue
        path = store.root / page["raw_path"]
        if not path.exists():
            page_issues.append({"url": page["url"], "error": "raw HTML missing"})
            continue
        if page["sha256"]:
            digest = sha256_file(path)
            if digest != page["sha256"]:
                page_issues.append({
                    "url": page["url"],
                    "error": f"raw HTML hash mismatch: {digest[:12]}",
                })
    paths_by_asset: dict[str, list] = defaultdict(list)
    for asset in store.iter_assets():
        if asset["status"] != "done":
            continue
        checked_assets += 1
        if not asset["local_path"]:
            asset_issues.append({"url": asset["url"], "error": "missing local_path"})
            continue
        path = store.root / asset["local_path"]
        if not path.exists():
            asset_issues.append({"url": asset["url"], "error": "blob missing"})
            continue
        if asset["sha256"]:
            digest = sha256_file(path)
            if digest != asset["sha256"]:
                asset_issues.append({
                    "url": asset["url"],
                    "error": f"blob hash mismatch: {digest[:12]}",
                })
            else:
                paths_by_asset[asset["local_path"]].append(asset["url"])
    if fix:
        for issue in page_issues:
            store.mark_page_bad(issue["url"], issue["error"])
        for issue in asset_issues:
            store.mark_asset_pending(issue["url"], issue["error"])
        for path, urls in paths_by_asset.items():
            if not any(item["url"] in urls for item in asset_issues):
                continue
            for url in urls:
                store.mark_asset_pending(url, "shared blob failed verification")
    for issue in page_issues:
        log(f"page issue: {issue['url']} ({issue['error']})")
    for issue in asset_issues:
        log(f"asset issue: {issue['url']} ({issue['error']})")
    summary = {
        "checked_pages": checked_pages,
        "checked_assets": checked_assets,
        "page_issues": page_issues,
        "asset_issues": asset_issues,
        "fixed": fix,
        "ok": not page_issues and not asset_issues,
    }
    if page_issues or asset_issues:
        total = sum(
            (store.root / asset["local_path"]).stat().st_size
            for asset in store.iter_assets()
            if asset["status"] == "done"
            and asset["local_path"]
            and (store.root / asset["local_path"]).exists()
        )
        log(f"verified {checked_pages} pages, {checked_assets} assets ({human_size(total)})")
    else:
        log(f"all checks passed: {checked_pages} pages, {checked_assets} assets")
    return summary
