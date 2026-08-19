import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from tts_policy import validate_manifest_voice_ids
from youtube_publishing import validate_publishing_copy


ORDER = ["hook", "setup", "cause", "turn", "consequence", "meaning"]
RUNTIME_CONTRACT = {"name": "chinese-wisdom-runtime", "version": 1, "mode": "shared-workspace"}
VISUAL_CONTRACT = {
    "outer_paper_margin_pct": {"min": 8, "max": 12},
    "visual_island": "centered-irregular-dry-brush",
    "corners": "substantially-clean",
    "platform_safe_region": {"x_min": 0.10, "x_max": 0.80, "y_min": 0.10, "y_max": 0.78},
    "motion_caps": {
        "min_scale": 1.04,
        "max_scale": 1.06,
        "min_pan_px": 24,
        "max_pan_x_px": 36,
        "max_pan_y_px": 36,
        "moving_scenes_min": 2,
        "moving_scenes_max": 3,
        "motion_mode": "single-direction-once",
    },
}
COPYRIGHT_MARK = {"text": "© CARTGO", "x": 120, "y": 210, "font_size": 36, "opacity": 0.55}


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc


def valid_iso_date(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def valid_http_url(value):
    parsed = urlparse(str(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalized_display(value):
    return " ".join(str(value).split())


def validate_motion(scene, errors):
    scene_id = scene.get("id")
    motion = scene.get("motion")
    if not isinstance(motion, dict):
        errors.append(f"scene {scene_id}: motion object is required")
        return False
    kind = motion.get("type")
    if kind == "none":
        if set(motion) != {"type"}:
            errors.append(f"scene {scene_id}: static motion may contain only type")
        return False
    if kind == "scale":
        if set(motion) != {"type", "from_scale", "to_scale"}:
            errors.append(f"scene {scene_id}: scale motion contains unsupported fields")
        start = float(motion.get("from_scale", 0))
        end = float(motion.get("to_scale", 0))
        if start != 1.0 or not 1.04 <= end <= 1.06:
            errors.append(f"scene {scene_id}: scale must move once from 1.0 to 1.04-1.06")
    elif kind == "pan":
        if set(motion) != {"type", "from_x_px", "to_x_px", "from_y_px", "to_y_px"}:
            errors.append(f"scene {scene_id}: pan motion contains unsupported fields")
        x0 = float(motion.get("from_x_px", 0))
        x1 = float(motion.get("to_x_px", 0))
        y0 = float(motion.get("from_y_px", 0))
        y1 = float(motion.get("to_y_px", 0))
        travel = max(abs(x1 - x0), abs(y1 - y0))
        if not 24 <= travel <= 36:
            errors.append(f"scene {scene_id}: pan dominant-axis travel must be 24-36 px")
    else:
        errors.append(f"scene {scene_id}: motion.type must be none, scale, or pan")
        return False
    if motion.get("loop") is True or motion.get("reverse") is True:
        errors.append(f"scene {scene_id}: motion cannot loop or reverse")
    return True


def validate_copyright_marks(scenes, spec_version, errors):
    for index, scene in enumerate(scenes, start=1):
        mark = scene.get("copyright_mark")
        if index == 2:
            if spec_version == 2 and mark != COPYRIGHT_MARK:
                errors.append("scene 02: copyright_mark must be the fixed © CARTGO top-left mark")
            elif mark is not None and mark != COPYRIGHT_MARK:
                errors.append("scene 02: copyright_mark must match the fixed © CARTGO contract")
        elif mark is not None:
            errors.append(f"scene {index:02d}: copyright_mark is allowed only on scene 02")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--workspace-dir")
    parser.add_argument("--phase", choices=("content", "full"), default="full")
    args = parser.parse_args()
    root = Path(args.project_dir).resolve()
    try:
        story = load_json(root / "storyboard.json")
        audio = load_json(root / "audio-manifest.json")
        publishing = load_json(root / "publishing.json")
        audio_result = load_json(root / "audio-result.json") if (root / "audio-result.json").is_file() else {}
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from None

    errors = []
    managed_project = (root / "episode-spec.json").is_file()
    managed_spec = {}
    spec_version = None
    if managed_project:
        try:
            managed_spec = load_json(root / "episode-spec.json")
            spec_version = managed_spec.get("version")
        except ValueError as exc:
            errors.append(str(exc))
        canonical_renderer = Path(__file__).resolve().parent.parent / "assets" / "project-template" / "index.jsx"
        project_renderer = root / "src" / "index.jsx"
        if spec_version == 2 and (not project_renderer.is_file() or project_renderer.read_bytes() != canonical_renderer.read_bytes()):
            errors.append("src/index.jsx must remain the canonical data-driven renderer; express episode changes in episode-spec.json")
        if spec_version not in {1, 2}:
            errors.append("episode-spec.version must be 1 or 2")
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
    for forbidden in ("node_modules", ".venv", "tts-cache"):
        if any(path.is_dir() for path in root.rglob(forbidden)):
            errors.append(f"episode must not contain local dependency or cache directory {forbidden}")
    for forbidden in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
        if any(path.is_file() for path in root.rglob(forbidden)):
            errors.append(f"episode must not contain {forbidden}; use the shared workspace")
    for duplicate in ("images", "audio", "music"):
        if (root / duplicate).exists():
            errors.append(f"episode media must live only under public; remove top-level {duplicate}")
    project = story.get("project", {})
    if project.get("runtime") != RUNTIME_CONTRACT:
        errors.append("project.runtime must use chinese-wisdom shared-workspace version 1")
    expected = {"ratio": "9:16", "width": 1080, "height": 1920, "fps": 30, "primary_language": "en"}
    for key, value in expected.items():
        if project.get(key) != value:
            errors.append(f"project.{key} must be {value!r}")
    if project.get("style") != "sunlit-storybook-9x16":
        errors.append("project.style must be 'sunlit-storybook-9x16'")
    if project.get("visual_contract") != VISUAL_CONTRACT:
        errors.append("project.visual_contract must match the cartoon paper-safe single-motion contract")
    if not 50 <= float(project.get("target_duration_sec", 0)) <= 65:
        errors.append("project.target_duration_sec must be 50-65")
    for key in ("idiom", "pinyin", "literal_gloss", "meaning"):
        if not str(project.get(key, "")).strip():
            errors.append(f"project.{key} is required")
    meaning_card = project.get("meaning_card")
    if not isinstance(meaning_card, dict):
        errors.append("project.meaning_card is required")
        meaning_card = {}
    for key in ("reflection", "source"):
        if not str(meaning_card.get(key, "")).strip():
            errors.append(f"project.meaning_card.{key} is required")
    for display_key, source_value in (
        ("meaning_display", project.get("meaning", "")),
        ("reflection_display", meaning_card.get("reflection", "")),
    ):
        display_value = meaning_card.get(display_key, source_value)
        if normalized_display(display_value) != normalized_display(source_value):
            errors.append(f"project.meaning_card.{display_key} may add line breaks only")
    if meaning_card.get("spoken_fields") != ["idiom", "meaning", "reflection"]:
        errors.append("project.meaning_card.spoken_fields must speak idiom, meaning, and reflection only")
    sources = story.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("at least one authoritative source is required")
    else:
        has_passage_source = False
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                errors.append(f"source {index}: must be an object")
                continue
            for key in ("url", "supports"):
                if not source.get(key):
                    errors.append(f"source {index}: {key} is required")
            if all(source.get(key) for key in ("passage", "work", "chapter")):
                has_passage_source = True
            accessed_on = source.get("accessed_on", source.get("access_date"))
            if not accessed_on:
                errors.append(f"source {index}: accessed_on is required")
            if source.get("url") and not valid_http_url(source.get("url")):
                errors.append(f"source {index}: url must be HTTP(S)")
            if accessed_on and not valid_iso_date(accessed_on):
                errors.append(f"source {index}: accessed_on must be YYYY-MM-DD")
            supports = source.get("supports")
            if supports and (not isinstance(supports, list) or any(not str(item).strip() for item in supports)):
                errors.append(f"source {index}: supports must be a non-empty list of supported beats or events")
        if not has_passage_source:
            errors.append("at least one source must record passage, work, and chapter")

    scenes = story.get("scenes", [])
    if [scene.get("narrative_function") for scene in scenes] != ORDER:
        errors.append(f"six scene functions must be {ORDER}")
    validate_copyright_marks(scenes, spec_version, errors)
    segments_by_id = {segment.get("id"): segment for segment in audio.get("segments", [])}
    segment_ids = set(segments_by_id)
    speakers = set(audio.get("voices", {}))
    total = 0.0
    moving_count = 0
    for index, scene in enumerate(scenes, start=1):
        expected_id = f"{index:02d}"
        if scene.get("id") != expected_id:
            errors.append(f"scene {index}: id must be {expected_id}")
        for key in ("image", "visual_description"):
            if not str(scene.get(key, "")).strip():
                errors.append(f"scene {scene.get('id')}: {key} is required")
        if scene.get("historicity") not in {"sourced", "inferred", "dramatized"}:
            errors.append(f"scene {scene.get('id')}: historicity must be sourced, inferred, or dramatized")
        if not isinstance(scene.get("segments"), list) or not scene.get("segments"):
            errors.append(f"scene {scene.get('id')}: at least one segment is required")
        total += float(scene.get("duration_sec", 0))
        moving_count += int(validate_motion(scene, errors))
        focus = scene.get("focus", {})
        if not (0 <= float(focus.get("x", -1)) <= 1 and 0 <= float(focus.get("y", -1)) <= 1):
            errors.append(f"scene {scene.get('id')}: focus coordinates must be normalized")
        for segment_id in scene.get("segments", []):
            if segment_id not in segment_ids:
                errors.append(f"scene {scene.get('id')}: unknown segment {segment_id}")
        dialogue_segments = [seg for seg in audio.get("segments", []) if seg.get("kind") == "dialogue" and seg.get("id") in scene.get("segments", [])]
        if dialogue_segments:
            if len(dialogue_segments) != 1 or len(scene.get("segments", [])) != 1:
                errors.append(f"scene {scene.get('id')}: dialogue scene must contain exactly one utterance")
            bubble = scene.get("bubble")
            if not isinstance(bubble, dict):
                errors.append(f"scene {scene.get('id')}: dialogue requires a nearby bubble")
            else:
                x = float(bubble.get("x", -1))
                y = float(bubble.get("y", -1))
                width = float(bubble.get("width", -1))
                tail = bubble.get("tail_to", {})
                tx = float(tail.get("x", -1))
                ty = float(tail.get("y", -1))
                if not (0.10 <= x < 0.80 and 0 < width <= 0.70 and x + width <= 0.80 and 0.10 <= y <= 0.65):
                    errors.append(f"scene {scene.get('id')}: bubble must stay inside the central safe region")
                if not (x <= tx <= x + width and y <= ty <= min(0.78, y + 0.25)):
                    errors.append(f"scene {scene.get('id')}: bubble tail must be short and aligned under the bubble")
    if moving_count not in {2, 3}:
        errors.append(f"exactly 2-3 scenes must move; found {moving_count}")
    if not 50 <= total <= 65:
        errors.append(f"scene durations total {total:.1f}s; expected 50-65s")

    meaning_scene = next((scene for scene in scenes if scene.get("narrative_function") == "meaning"), {})
    meaning_segments = [segments_by_id.get(segment_id) for segment_id in meaning_scene.get("segments", [])]
    if len(meaning_segments) != 3 or any(segment is None for segment in meaning_segments):
        errors.append("meaning scene must reference exactly three valid spoken segments")
    else:
        expected_meaning = [
            ("idiom", "zh-CN", str(project.get("idiom", "")), "zh-CN"),
            ("meaning", "en-US", str(project.get("meaning", "")), "en-US"),
            ("reflection", "en-US", str(meaning_card.get("reflection", "")), "en-US"),
        ]
        for segment, (role, language, text, native_language) in zip(meaning_segments, expected_meaning):
            if segment.get("spoken_role") != role:
                errors.append(f"meaning segment {segment.get('id')}: spoken_role must be {role}")
            if segment.get("language") != language:
                errors.append(f"meaning segment {segment.get('id')}: language must be {language}")
            if str(segment.get("text", "")).strip() != text.strip():
                errors.append(f"meaning segment {segment.get('id')}: text must exactly match project {role}")
            profile = audio.get("voices", {}).get(segment.get("speaker"), {})
            if profile.get("native_language") != native_language:
                errors.append(f"meaning segment {segment.get('id')}: speaker must be native {native_language}")
        if meaning_segments[0].get("speaker") == meaning_segments[1].get("speaker"):
            errors.append("meaning scene must use separate Mandarin and English voice profiles")
        if not 400 <= int(meaning_segments[0].get("pause_after_ms", 0)) <= 600:
            errors.append("spoken idiom must be followed by a 400-600 ms pause")
    forbidden_roles = {"pinyin", "source"}
    if any(segment.get("spoken_role") in forbidden_roles for segment in audio.get("segments", [])):
        errors.append("pinyin and source citation must remain visible but unspoken")

    tts = audio.get("tts", {})
    if tts.get("primary") != {"provider": "mimo", "model": "mimo-v2.5-tts"}:
        errors.append("tts.primary must be MiMo mimo-v2.5-tts")
    if tts.get("fallback", {}).get("provider") != "edge-tts":
        errors.append("tts.fallback.provider must be edge-tts")
    if tts.get("fallback_scope") != "whole_video" or tts.get("fallback_requires_approval") is not True:
        errors.append("Edge fallback must be whole-video and require explicit approval")
    if audio.get("language") != "en-with-zh-idiom":
        errors.append("audio language must be en-with-zh-idiom")
    errors.extend(validate_manifest_voice_ids(audio))
    for speaker, profile in audio.get("voices", {}).items():
        for key in ("mimo_voice", "edge_voice", "native_language", "style"):
            if not str(profile.get(key, "")).strip():
                errors.append(f"voice {speaker}: {key} is required")
    for segment in audio.get("segments", []):
        for key in ("id", "scene_id", "speaker", "kind", "language", "text", "emotion", "pause_after_ms"):
            if key not in segment:
                errors.append(f"segment {segment.get('id')}: {key} is required")
        if segment.get("speaker") not in speakers:
            errors.append(f"segment {segment.get('id')}: missing voice for {segment.get('speaker')}")
        if not str(segment.get("text", "")).strip():
            errors.append(f"segment {segment.get('id')}: text is required")
        if segment.get("language") not in {"en-US", "zh-CN"}:
            errors.append(f"segment {segment.get('id')}: language must be en-US or zh-CN")
        if managed_project and segment.get("kind") == "narration" and not segment.get("spoken_role"):
            pages = segment.get("caption_pages")
            if not isinstance(pages, list) or not pages:
                errors.append(f"segment {segment.get('id')}: narration requires caption_pages")
            else:
                if any(len(str(page).splitlines()) > 2 for page in pages):
                    errors.append(f"segment {segment.get('id')}: every caption page must contain at most two lines")
                if normalized_display(" ".join(str(page) for page in pages)) != normalized_display(segment.get("text", "")):
                    errors.append(f"segment {segment.get('id')}: caption_pages must exactly match spoken text apart from line breaks")

    rendered_by_id = {segment.get("id"): segment for segment in audio_result.get("segments", [])}
    if managed_project and args.phase == "full" and not rendered_by_id:
        errors.append("audio-result.json must contain synthesized segments before full validation")
    if rendered_by_id:
        for scene in scenes:
            rendered_duration = 0.0
            ids = scene.get("segments", [])
            for index, segment_id in enumerate(ids):
                rendered = rendered_by_id.get(segment_id)
                segment = segments_by_id.get(segment_id, {})
                if not rendered:
                    errors.append(f"audio-result.json is missing segment {segment_id}")
                    continue
                rendered_duration += float(rendered.get("duration_sec", 0))
                if index < len(ids) - 1:
                    rendered_duration += int(segment.get("pause_after_ms", 0)) / 1000
            if rendered_duration > float(scene.get("duration_sec", 0)):
                errors.append(
                    f"scene {scene.get('id')}: rendered speech timeline {rendered_duration:.2f}s "
                    f"does not fit duration {float(scene.get('duration_sec', 0)):.2f}s"
                )

    if args.phase == "content":
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            raise SystemExit(1)
        print(f"OK: content contract valid - 6 scenes - {moving_count} moving - {total:.1f}s - MiMo primary")
        return

    if not publishing.get("tiktok") or not publishing.get("youtube_shorts"):
        errors.append("publishing copy for TikTok and YouTube Shorts is required")
    errors.extend(validate_publishing_copy(publishing))
    checked_on = valid_iso_date(publishing.get("platform_checked_on"))
    if checked_on is None:
        errors.append("publishing.platform_checked_on must be YYYY-MM-DD")
    elif checked_on > date.today() or checked_on < date.today() - timedelta(days=7):
        errors.append("publishing.platform_checked_on must be within the last 7 days and not in the future")
    official_urls = publishing.get("official_platform_sources")
    if not isinstance(official_urls, list) or not official_urls:
        errors.append("publishing.official_platform_sources must be a non-empty list")
    else:
        hosts = []
        for item in official_urls:
            url = item.get("url") if isinstance(item, dict) else item
            if not valid_http_url(url):
                errors.append("publishing official platform sources must be HTTP(S) URLs")
                continue
            hosts.append(urlparse(url).netloc.lower())
        if not any(host == "tiktok.com" or host.endswith(".tiktok.com") for host in hosts):
            errors.append("publishing official sources must include an official TikTok URL")
        if not any(host == "youtube.com" or host.endswith(".youtube.com") or host == "support.google.com" for host in hosts):
            errors.append("publishing official sources must include an official YouTube URL")
    tiktok = publishing.get("tiktok", {})
    if not str(tiktok.get("caption", "")).strip():
        errors.append("publishing.tiktok.caption is required")
    tiktok_hashtags = tiktok.get("hashtags")
    if not isinstance(tiktok_hashtags, list) or not tiktok_hashtags or any(
        not isinstance(item, str) or not item.startswith("#") or any(char.isspace() for char in item)
        for item in tiktok_hashtags
    ):
        errors.append("publishing.tiktok.hashtags must be non-empty #Hashtags without spaces")
    for key in ("source_note", "music_credit"):
        if not str(publishing.get(key, "")).strip():
            errors.append(f"publishing.{key} is required")
    if managed_project:
        music = publishing.get("music", {})
        if not str(music.get("file", "")).startswith("music/"):
            errors.append("publishing.music.file must be a public-relative music/ path")
        try:
            if not 0 < float(music.get("volume", 0)) <= 0.25:
                errors.append("publishing.music.volume must be above 0 and at most 0.25")
        except (TypeError, ValueError):
            errors.append("publishing.music.volume must be numeric")
    cover = publishing.get("cover", {})
    if cover.get("file") != "out/cover.png":
        errors.append("publishing.cover.file must be out/cover.png")
    for key in ("title", "visual_hook", "selection_reason"):
        if not str(cover.get(key, "")).strip():
            errors.append(f"publishing.cover.{key} is required")
    title_words = str(cover.get("title", "")).split()
    if title_words and not 3 <= len(title_words) <= 6:
        errors.append("publishing.cover.title must contain 3-6 words")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"OK: project contract valid - 6 scenes - {moving_count} moving - {total:.1f}s - MiMo primary")


if __name__ == "__main__":
    main()
