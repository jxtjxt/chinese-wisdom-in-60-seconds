#!/usr/bin/env python3
"""Prepare or inspect the versioned shared Remotion workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


RUNTIME_NAME = "chinese-wisdom-runtime-v1"
TEMPLATE_FILES = ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml")
MARKER_NAME = ".chinese-wisdom-runtime.json"


def template_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "shared-runtime-v1"


def dependency_fingerprint(source: Path | None = None) -> str:
    source = source or template_dir()
    digest = hashlib.sha256()
    for name in TEMPLATE_FILES:
        path = source / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def read_marker(workspace: Path) -> dict:
    path = workspace / MARKER_NAME
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def needs_install(workspace: Path, fingerprint: str) -> bool:
    marker = read_marker(workspace)
    return not (
        (workspace / "node_modules").is_dir()
        and marker.get("runtime") == RUNTIME_NAME
        and marker.get("dependency_fingerprint") == fingerprint
        and marker.get("dependencies_installed") is True
    )


def sync_templates(workspace: Path, source: Path) -> None:
    marker = read_marker(workspace)
    owned = marker.get("runtime") == RUNTIME_NAME
    for name in TEMPLATE_FILES:
        target = workspace / name
        template = source / name
        if target.exists() and target.read_bytes() != template.read_bytes() and not owned:
            raise ValueError(f"refusing to overwrite unowned workspace file: {target}")
        if not target.exists() or target.read_bytes() != template.read_bytes():
            shutil.copy2(template, target)


def write_marker(workspace: Path, fingerprint: str) -> None:
    payload = {
        "runtime": RUNTIME_NAME,
        "dependency_fingerprint": fingerprint,
        "dependencies_installed": True,
    }
    temporary = workspace / f"{MARKER_NAME}.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, workspace / MARKER_NAME)


def acquire_lock(workspace: Path, timeout_sec: int = 300) -> tuple[int, Path]:
    path = workspace / ".chinese-wisdom-install.lock"
    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(handle, str(os.getpid()).encode("ascii"))
            return handle, path
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for shared runtime lock: {path}")
            time.sleep(1)


def default_workspace() -> Path:
    configured = os.environ.get("CHINESE_WISDOM_WORKSPACE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "CodexWorkspaces" / "chinese-wisdom-v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-dir", type=Path, default=default_workspace())
    parser.add_argument("--status", action="store_true", help="inspect without changing files")
    parser.add_argument("--skip-install", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    workspace = args.workspace_dir.expanduser().resolve()
    source = template_dir()
    fingerprint = dependency_fingerprint(source)
    if args.status:
        templates_match = all(
            (workspace / name).is_file()
            and (workspace / name).read_bytes() == (source / name).read_bytes()
            for name in TEMPLATE_FILES
        )
        healthy = templates_match and not needs_install(workspace, fingerprint)
        print(f"{'OK' if healthy else 'NOT_READY'}: {workspace} - {RUNTIME_NAME}")
        raise SystemExit(0 if healthy else 1)

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "episodes").mkdir(exist_ok=True)
    (workspace / ".cache" / "tts").mkdir(parents=True, exist_ok=True)
    (workspace / ".cache" / "renders").mkdir(parents=True, exist_ok=True)
    sync_templates(workspace, source)
    if args.skip_install:
        print(f"OK: shared workspace files prepared; dependency install skipped - {workspace}")
        return
    if not needs_install(workspace, fingerprint):
        print(f"OK: reused shared dependencies - {workspace}")
        return

    handle, lock_path = acquire_lock(workspace)
    try:
        if not needs_install(workspace, fingerprint):
            print(f"OK: reused shared dependencies - {workspace}")
            return
        pnpm = shutil.which("pnpm")
        if not pnpm:
            raise RuntimeError("pnpm is required but was not found on PATH")
        subprocess.run(
            [pnpm, "install", "--frozen-lockfile"],
            cwd=workspace,
            check=True,
        )
        write_marker(workspace, fingerprint)
        print(f"OK: installed shared dependencies once - {workspace}")
    finally:
        os.close(handle)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, TimeoutError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
