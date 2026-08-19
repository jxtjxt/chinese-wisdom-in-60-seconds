#!/usr/bin/env python3
"""Read or record a compact seven-day cache of verified official platform sources."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from ensure_shared_workspace import default_workspace


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("checked-on must be YYYY-MM-DD") from exc


def valid_sources(values: list[str]) -> bool:
    hosts = [urlparse(value).netloc.lower() for value in values]
    return (
        all(urlparse(value).scheme in {"http", "https"} and urlparse(value).netloc for value in values)
        and any(host == "tiktok.com" or host.endswith(".tiktok.com") for host in hosts)
        and any(host == "youtube.com" or host.endswith(".youtube.com") or host == "support.google.com" for host in hosts)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-dir", type=Path, default=default_workspace())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    record = subparsers.add_parser("record")
    record.add_argument("--checked-on", required=True)
    record.add_argument("--source", action="append", required=True)
    args = parser.parse_args()

    path = args.workspace_dir.expanduser().resolve() / ".cache" / "platform-policy.json"
    if args.command == "status":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            checked_on = parse_date(str(value.get("checked_on", "")))
            sources = value.get("sources") or []
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            print("MISS: no valid platform verification cache")
            return
        if checked_on > date.today() or checked_on < date.today() - timedelta(days=7) or not valid_sources(sources):
            print("MISS: platform verification cache is expired or invalid")
            return
        print(json.dumps({"status": "HIT", "checked_on": checked_on.isoformat(), "sources": sources}, separators=(",", ":")))
        return

    checked_on = parse_date(args.checked_on)
    if checked_on != date.today():
        raise ValueError("new platform verification must use today's date")
    if not valid_sources(args.source):
        raise ValueError("sources must include official TikTok and YouTube URLs")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"checked_on": checked_on.isoformat(), "sources": args.source}, indent=2) + "\n", encoding="utf-8")
    print(f"OK: recorded platform verification cache - {path}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
