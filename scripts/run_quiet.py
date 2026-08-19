#!/usr/bin/env python3
"""Run a verbose command, save its complete log, and print only a compact result."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from collections import deque
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--tail-lines", type=int, default=60)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise ValueError("command is required after --")
    if args.tail_lines < 1:
        raise ValueError("--tail-lines must be positive")
    resolved = shutil.which(command[0])
    if resolved:
        command[0] = resolved

    log = args.log.expanduser().resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    tail: deque[str] = deque(maxlen=args.tail_lines)
    with log.open("w", encoding="utf-8", errors="replace") as handle:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            handle.write(line)
            tail.append(line.rstrip())
        return_code = process.wait()

    if return_code:
        print(f"ERROR: command failed with exit code {return_code}; log: {log}")
        for line in tail:
            print(line)
        raise SystemExit(return_code)
    print(f"OK: command completed; log: {log}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
