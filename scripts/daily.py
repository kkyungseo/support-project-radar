"""
scripts/daily.py

Simplified daily.py
- Fetch data from sources
- Filter based on keywords
- Send results to Slack
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from pathlib import Path

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent / 'src'))

from radar.connectors.knowhow_feed import _parse_rss_with_feedparser
from radar.integrations.slack import send_to_slack

@dataclass
class DailyContext:
    # 어떤 소스를 돌릴지 (None => sources.yaml에서 enabled=true 전체)
    sources: Optional[List[str]] = None

    # publish 제어
    dry_run: bool = True
    publish_enabled: bool = False

    # 안전장치/디버그
    max_items: Optional[int] = None
    verbose: bool = False

    # 추가 옵션(향후 확장)
    extras: Dict[str, Any] = field(default_factory=dict)


def _log(msg: str) -> None:
    print(f"[daily] {msg}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="daily",
        description="Run daily grant radar pipeline and (optionally) publish to Slack.",
    )

    p.add_argument(
        "--sources",
        type=str,
        default="",
        help='Comma-separated source ids to run (e.g. "kstartup,knowhow"). Empty => all enabled.',
    )

    p.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish results (Slack/DB/etc). If omitted, runs in dry-run mode.",
    )

    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run (do not publish). This is default unless --publish is set.",
    )

    p.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Hard cap on number of items to process after normalize (useful for testing).",
    )

    p.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging (prints exception tracebacks).",
    )

    return p


def _parse_sources(s: str) -> Optional[List[str]]:
    s = s.strip()
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def validate_ctx(ctx: DailyContext) -> None:
    # Default: dry-run unless explicit publish
    if ctx.publish_enabled:
        ctx.dry_run = False
    else:
        ctx.dry_run = True


# Removed pipeline dependency and replaced with placeholder functions

def fetch_data_from_sites(ctx: DailyContext):
    # Placeholder for fetching data from three sites
    return [
        {"site": "Site A", "data": "Sample data A"},
        {"site": "Site B", "data": "Sample data B"},
        {"site": "Site C", "data": "Sample data C"},
    ]


def process_data(data):
    # Placeholder for processing data
    return [item for item in data if "Sample" in item["data"]]


def display_data(data):
    # Display collected data in the terminal
    _log("Collected Data:")
    for item in data:
        _log(f"- {item['site']}: {item['data']}")


# Replace pipeline steps with new logic

def run_pipeline(ctx: DailyContext) -> int:
    started_at = datetime.now().astimezone()
    _log(f"started at: {started_at.isoformat(timespec='seconds')}")
    _log(f"sources: {','.join(ctx.sources) if ctx.sources else 'ALL (enabled)'}")
    _log(f"mode: {'PUBLISH' if ctx.publish_enabled else 'DRY-RUN'}")

    # ---- 1) Fetch
    _log("step: fetch_data_from_sites")
    raw_items = fetch_data_from_sites(ctx)
    _log(f"fetched: {len(raw_items):,}")

    # ---- 2) Process
    _log("step: process_data")
    processed_items = process_data(raw_items)
    _log(f"processed: {len(processed_items):,}")

    # ---- 3) Display
    _log("step: display_data")
    display_data(processed_items)

    # ---- 4) Publish (optional)
    if ctx.publish_enabled:
        _log("step: publish to Slack")
        for item in processed_items:
            send_to_slack(f"Site: {item['site']}, Data: {item['data']}")
        _log("publish: done")
    else:
        _log("publish: skipped (dry-run)")

    finished_at = datetime.now().astimezone()
    _log(f"finished at: {finished_at.isoformat(timespec='seconds')}")
    _log(f"duration: {finished_at - started_at}")

    # Exit code 0 even if no items; not an error.
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    ctx = DailyContext(
        sources=_parse_sources(args.sources),
        publish_enabled=bool(args.publish) and not bool(args.dry_run),
        dry_run=bool(args.dry_run) or not bool(args.publish),
        max_items=args.max_items,
        verbose=args.verbose,
        extras={
            "invoked_by": "scripts/daily.py",
            "run_type": "daily",
            "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        },
    )

    validate_ctx(ctx)

    try:
        return run_pipeline(ctx)
    except KeyboardInterrupt:
        _log("interrupted by user")
        return 130
    except Exception as e:
        _log(f"ERROR: {e}")
        if ctx.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    main()