#!/usr/bin/env python3
"""Initialize one episode with a compact spec and the shared data-driven renderer."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from ensure_shared_workspace import default_workspace


SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEMPLATE_NAMES = ("episode-spec.json",)


def write_new(path: Path, data: bytes) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-dir", type=Path, default=default_workspace())
    parser.add_argument("--slug", required=True)
    parser.add_argument("--idiom", default="")
    parser.add_argument("--skip-runtime-install", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not SLUG_RE.fullmatch(args.slug):
        raise ValueError("slug must contain lowercase letters, digits, and single hyphens only")

    skill_root = Path(__file__).resolve().parent.parent
    workspace = args.workspace_dir.expanduser().resolve()
    episode = workspace / "episodes" / args.slug
    if episode.exists() and any(episode.iterdir()):
        raise ValueError(f"refusing to initialize non-empty episode: {episode}")

    ensure_command = [
        sys.executable,
        str(skill_root / "scripts" / "ensure_shared_workspace.py"),
        "--workspace-dir",
        str(workspace),
    ]
    if args.skip_runtime_install:
        ensure_command.append("--skip-install")
    subprocess.run(ensure_command, check=True)

    episode.mkdir(parents=True, exist_ok=True)

    template_dir = skill_root / "assets" / "project-template"
    for name in TEMPLATE_NAMES:
        source = template_dir / name
        payload = source.read_bytes()
        if name == "episode-spec.json" and args.idiom.strip():
            value = json.loads(payload.decode("utf-8"))
            value["project"]["idiom"] = args.idiom.strip()
            payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        write_new(episode / name, payload)

    write_new(
        episode / "src" / "CenteredBlock.jsx",
        (template_dir / "CenteredBlock.jsx").read_bytes(),
    )
    write_new(episode / "src" / "index.jsx", (template_dir / "index.jsx").read_bytes())
    write_new(
        episode / "audio-result.json",
        (json.dumps({"version": 1, "segments": []}, indent=2) + "\n").encode("utf-8"),
    )
    for relative in (
        "public/images",
        "public/audio",
        "public/music",
        "evidence/sources",
        "evidence/music",
        "qa",
        "out",
    ):
        (episode / relative).mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            str(skill_root / "scripts" / "compile_episode.py"),
            "--project-dir",
            str(episode),
        ],
        check=True,
    )

    print(f"OK: initialized episode - {episode}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
