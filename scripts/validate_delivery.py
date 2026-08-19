import argparse
import json
import os
import subprocess
from pathlib import Path

from youtube_publishing import OUTPUT_NAME, render_markdown


MAX_MP4_BYTES = 10_000_000
RUNTIME_CONTRACT = {"name": "chinese-wisdom-runtime", "version": 1, "mode": "shared-workspace"}


def probe(path: Path):
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ValueError("ffprobe is required but was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(exc.stderr.strip() or f"ffprobe failed for {path}") from exc
    return json.loads(result.stdout)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid or missing JSON: {path}: {exc}") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--workspace-dir")
    args = parser.parse_args()
    root = Path(args.project_dir).resolve()
    output_dir = root / "out"
    errors = []
    configured_workspace = args.workspace_dir or os.environ.get("CHINESE_WISDOM_WORKSPACE")
    if not configured_workspace:
        errors.append("--workspace-dir or CHINESE_WISDOM_WORKSPACE is required")
        workspace = None
    else:
        workspace = Path(configured_workspace).expanduser().resolve()
        try:
            root.relative_to(workspace / "episodes")
        except ValueError:
            errors.append("project must be located below <workspace>/episodes")
        for required in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "node_modules"):
            if not (workspace / required).exists():
                errors.append(f"shared workspace is not ready: missing {required}")

    try:
        story = load_json(root / "storyboard.json")
        if story.get("project", {}).get("runtime") != RUNTIME_CONTRACT:
            errors.append("project.runtime must use chinese-wisdom shared-workspace version 1")
    except ValueError as exc:
        errors.append(str(exc))
    for forbidden in ("node_modules", ".venv", "tts-cache"):
        if any(path.is_dir() for path in root.rglob(forbidden)):
            errors.append(f"episode must not contain local dependency or cache directory {forbidden}")
    for forbidden in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
        if any(path.is_file() for path in root.rglob(forbidden)):
            errors.append(f"episode must not contain {forbidden}; use the shared workspace")
    for duplicate in ("images", "audio", "music"):
        if (root / duplicate).exists():
            errors.append(f"episode media must live only under public; remove top-level {duplicate}")
    if any(path.exists() for pattern in ("tts-output*", ".work") for path in root.glob(pattern)):
        errors.append("delivery must not retain episode-local TTS batches or .work directories")
    qa_dir = root / "qa"
    if qa_dir.exists():
        retained_intermediates = []
        for path in qa_dir.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            pass_artifact = "pass" in name and (name.endswith(".log") or ".log." in name or name.endswith(".mbtree"))
            if (name.startswith("master") and path.suffix.lower() == ".mp4") or pass_artifact or (name.startswith("render") and ".log" in name):
                retained_intermediates.append(path.name)
        if retained_intermediates:
            errors.append(f"delivery retains reproducible QA intermediates: {sorted(retained_intermediates)}")

    mp4s = list(output_dir.rglob("*.mp4")) if output_dir.exists() else []
    if len(mp4s) != 1 or (mp4s and mp4s[0].name != "chinese-wisdom-short.mp4"):
        errors.append(f"out must contain exactly chinese-wisdom-short.mp4; found {[p.name for p in mp4s]}")
    else:
        mp4 = mp4s[0]
        if mp4.stat().st_size >= MAX_MP4_BYTES:
            errors.append(f"MP4 must be below {MAX_MP4_BYTES} bytes; got {mp4.stat().st_size}")
        try:
            info = probe(mp4)
            streams = info.get("streams", [])
            video = next((s for s in streams if s.get("codec_type") == "video"), {})
            audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
            duration = float(info.get("format", {}).get("duration", 0))
            if (video.get("width"), video.get("height")) != (1080, 1920):
                errors.append(f"video must be 1080x1920; got {video.get('width')}x{video.get('height')}")
            if video.get("codec_name") != "h264":
                errors.append("video codec must be H.264")
            if audio.get("codec_name") != "aac":
                errors.append("audio codec must be AAC")
            if int(audio.get("sample_rate", 0)) != 48000 or int(audio.get("channels", 0)) != 2:
                errors.append("audio must be stereo 48 kHz")
            if not 50 <= duration <= 65:
                errors.append(f"duration must be 50-65s; got {duration:.2f}s")
            rate = video.get("r_frame_rate", "0/1").split("/")
            fps = float(rate[0]) / float(rate[1]) if len(rate) == 2 and float(rate[1]) else 0
            if abs(fps - 30) > 0.01:
                errors.append(f"video must be 30 fps; got {fps:.3f}")
        except ValueError as exc:
            errors.append(str(exc))

    pngs = list(output_dir.glob("*.png")) if output_dir.exists() else []
    cover = output_dir / "cover.png"
    if pngs != [cover] and sorted(p.name for p in pngs) != ["cover.png"]:
        errors.append(f"out must contain exactly cover.png as its PNG; found {[p.name for p in pngs]}")
    elif cover.is_file():
        try:
            cover_info = probe(cover)
            image = next((s for s in cover_info.get("streams", []) if s.get("codec_type") == "video"), {})
            if (image.get("width"), image.get("height")) != (1080, 1920):
                errors.append(f"cover must be 1080x1920; got {image.get('width')}x{image.get('height')}")
        except ValueError as exc:
            errors.append(str(exc))
    else:
        errors.append("missing out/cover.png")

    markdowns = list(output_dir.glob("*.md")) if output_dir.exists() else []
    publishing_markdown = output_dir / OUTPUT_NAME
    if markdowns != [publishing_markdown] and sorted(path.name for path in markdowns) != [OUTPUT_NAME]:
        errors.append(f"out must contain exactly {OUTPUT_NAME} as its Markdown file; found {[path.name for path in markdowns]}")
    elif publishing_markdown.is_file():
        try:
            publishing = load_json(root / "publishing.json")
            expected_markdown = render_markdown(publishing)
            actual_markdown = publishing_markdown.read_text(encoding="utf-8")
            if actual_markdown != expected_markdown:
                errors.append(f"out/{OUTPUT_NAME} must exactly match publishing.json; regenerate it")
        except (ValueError, UnicodeDecodeError) as exc:
            errors.append(str(exc))
    else:
        errors.append(f"missing out/{OUTPUT_NAME}")

    for required in ("storyboard.json", "audio-manifest.json", "publishing.json", "audio-result.json"):
        if not (root / required).exists():
            errors.append(f"missing {required}")

    if (root / "audio-result.json").is_file():
        try:
            result = load_json(root / "audio-result.json")
            manifest = load_json(root / "audio-manifest.json")
            actual = result.get("actual_tts")
            if result.get("requested_tts") != "mimo-v2.5-tts" or actual not in {"mimo", "edge-tts"}:
                errors.append("audio-result must record MiMo request and a valid actual provider")
            if actual == "mimo" and (result.get("fallback_used") or result.get("fallback_approved")):
                errors.append("MiMo delivery cannot claim fallback use or approval")
            if actual == "edge-tts" and not (result.get("fallback_used") and result.get("fallback_approved") and result.get("fallback_reason")):
                errors.append("Edge delivery requires whole-video fallback approval and reason")
            result_segments = result.get("segments", [])
            manifest_segments = manifest.get("segments", [])
            if len(result_segments) != len(manifest_segments):
                errors.append("audio-result segment count must match audio-manifest")
            else:
                for rendered, planned in zip(result_segments, manifest_segments):
                    for key in ("id", "speaker", "language", "spoken_role", "text"):
                        if rendered.get(key) != planned.get(key):
                            errors.append(f"audio-result segment {rendered.get('id')}: {key} must match audio-manifest")
            if any(float(item.get("duration_sec", 0) or 0) <= 0 for item in result_segments):
                errors.append("every audio-result segment must record a positive duration_sec")
            segment_paths = [str(item.get("path", "")) for item in result_segments]
            provider_dir = "mimo" if actual == "mimo" else "edge-tts"
            if segment_paths and not all(provider_dir in Path(path).parts for path in segment_paths):
                errors.append("audio-result contains paths outside the single actual provider batch")
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"OK: delivery valid - {mp4s[0].stat().st_size} bytes - 1080x1920 H.264/AAC - cover 1080x1920 - YouTube publishing Markdown")


if __name__ == "__main__":
    main()
