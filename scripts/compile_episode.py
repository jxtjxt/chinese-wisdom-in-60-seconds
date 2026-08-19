#!/usr/bin/env python3
"""Compile one compact episode spec into the canonical project manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ORDER = ["hook", "setup", "cause", "turn", "consequence", "meaning"]
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
TTS_CONTRACT = {
    "primary": {"provider": "mimo", "model": "mimo-v2.5-tts"},
    "fallback": {"provider": "edge-tts"},
    "fallback_scope": "whole_video",
    "fallback_requires_approval": True,
    "max_retries": 2,
}
DEFAULT_VOICES = {
    "narrator": {
        "mimo_voice": "Mia",
        "edge_voice": "en-US-JennyNeural",
        "native_language": "en-US",
        "style": "Warm, curious, concise native English narration",
    },
    "mandarin_teacher": {
        "mimo_voice": "mimo_default",
        "edge_voice": "zh-CN-XiaoxiaoNeural",
        "native_language": "zh-CN",
        "style": "Natural standard Mandarin with clear native tones",
    },
}


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid or missing {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def required_text(value: dict, key: str, context: str) -> str:
    text = str(value.get(key, "")).strip()
    if not text:
        raise ValueError(f"{context}.{key} is required")
    return text


def compile_scene(scene: dict, index: int) -> tuple[dict, list[dict]]:
    scene_id = f"{index:02d}"
    expected_function = ORDER[index - 1]
    if scene.get("narrative_function") != expected_function:
        raise ValueError(f"scene {scene_id}.narrative_function must be {expected_function}")
    output = {
        "id": scene_id,
        "narrative_function": expected_function,
        "image": str(scene.get("image") or f"images/{scene_id}.png"),
        "visual_description": required_text(scene, "visual_description", f"scene {scene_id}"),
        "duration_sec": scene.get("duration_sec"),
        "historicity": scene.get("historicity"),
        "focus": scene.get("focus", {"x": 0.5, "y": 0.5}),
        "motion": scene.get("motion", {"type": "none"}),
    }
    for optional in ("bubble", "caption_layout", "copyright_mark"):
        if optional in scene:
            output[optional] = scene[optional]

    if expected_function == "meaning":
        output["segments"] = ["s06-zh", "s06-meaning", "s06-reflection"]
        return output, []

    utterances = scene.get("utterances")
    if not isinstance(utterances, list) or not utterances:
        raise ValueError(f"scene {scene_id}.utterances must be a non-empty list")
    segments = []
    ids = []
    for utterance_index, utterance in enumerate(utterances, start=1):
        segment_id = str(utterance.get("id") or (f"s{scene_id}" if len(utterances) == 1 else f"s{scene_id}-{utterance_index}"))
        text = required_text(utterance, "text", f"scene {scene_id} utterance {utterance_index}")
        kind = str(utterance.get("kind", "narration"))
        segment = {
            "id": segment_id,
            "scene_id": scene_id,
            "speaker": str(utterance.get("speaker", "narrator")),
            "kind": kind,
            "language": str(utterance.get("language", "en-US")),
            "text": text,
            "emotion": str(utterance.get("emotion", "clear")),
            "pause_after_ms": int(utterance.get("pause_after_ms", 250)),
        }
        if kind == "narration":
            pages = utterance.get("caption_pages", [text])
            if not isinstance(pages, list) or not pages or any(not str(page).strip() for page in pages):
                raise ValueError(f"segment {segment_id}.caption_pages must be a non-empty list")
            segment["caption_pages"] = [str(page).strip() for page in pages]
        segments.append(segment)
        ids.append(segment_id)
    output["segments"] = ids
    return output, segments


def compile_spec(spec: dict) -> tuple[dict, dict, dict]:
    if spec.get("version") not in {1, 2}:
        raise ValueError("episode-spec.version must be 1 or 2")
    project_spec = spec.get("project")
    if not isinstance(project_spec, dict):
        raise ValueError("episode-spec.project is required")
    idiom = required_text(project_spec, "idiom", "project")
    meaning = required_text(project_spec, "meaning", "project")
    reflection = required_text(project_spec, "reflection", "project")
    meaning_source = required_text(project_spec, "meaning_source", "project")
    project = {
        "title": str(project_spec.get("title", "Chinese Wisdom in 60 Seconds")),
        "idiom": idiom,
        "pinyin": required_text(project_spec, "pinyin", "project"),
        "literal_gloss": required_text(project_spec, "literal_gloss", "project"),
        "meaning": meaning,
        "meaning_card": {
            "reflection": reflection,
            "source": meaning_source,
            "spoken_fields": ["idiom", "meaning", "reflection"],
            "meaning_display": str(project_spec.get("meaning_display", meaning)),
            "reflection_display": str(project_spec.get("reflection_display", reflection)),
        },
        "input_type": str(project_spec.get("input_type", "idiom")),
        "primary_language": "en",
        "cultural_language": "zh-Hans",
        "platforms": ["tiktok", "youtube-shorts"],
        "ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "target_duration_sec": project_spec.get("target_duration_sec", 60),
        "runtime": {"name": "chinese-wisdom-runtime", "version": 1, "mode": "shared-workspace"},
        "style": "sunlit-storybook-9x16",
        "visual_contract": VISUAL_CONTRACT,
    }
    if "meaning_layout" in project_spec:
        project["meaning_card"]["layout"] = project_spec["meaning_layout"]

    scene_specs = spec.get("scenes")
    if not isinstance(scene_specs, list) or len(scene_specs) != 6:
        raise ValueError("episode-spec.scenes must contain exactly six scenes")
    scenes = []
    segments = []
    for index, scene_spec in enumerate(scene_specs, start=1):
        scene, scene_segments = compile_scene(scene_spec, index)
        scenes.append(scene)
        segments.extend(scene_segments)

    idiom_segment = {"id": "s06-zh", "scene_id": "06", "speaker": "mandarin_teacher", "kind": "narration", "spoken_role": "idiom", "language": "zh-CN", "text": idiom, "emotion": "clear", "pause_after_ms": 500}
    if str(project_spec.get("idiom_tts_text", "")).strip():
        idiom_segment["tts_text"] = str(project_spec["idiom_tts_text"]).strip()
    segments.extend(
        [
            idiom_segment,
            {"id": "s06-meaning", "scene_id": "06", "speaker": "narrator", "kind": "narration", "spoken_role": "meaning", "language": "en-US", "text": meaning, "emotion": "clear", "pause_after_ms": 250},
            {"id": "s06-reflection", "scene_id": "06", "speaker": "narrator", "kind": "narration", "spoken_role": "reflection", "language": "en-US", "text": reflection, "emotion": "reflective", "pause_after_ms": 400},
        ]
    )
    voices = dict(DEFAULT_VOICES)
    voices.update(spec.get("voices") or {})
    story = {
        "version": 1,
        "project": project,
        "characters": spec.get("characters") or [],
        "sources": spec.get("sources") or [],
        "scenes": scenes,
    }
    audio = {"version": 1, "language": "en-with-zh-idiom", "tts": TTS_CONTRACT, "voices": voices, "segments": segments}

    publishing_spec = spec.get("publishing")
    if not isinstance(publishing_spec, dict):
        raise ValueError("episode-spec.publishing is required")
    music = publishing_spec.get("music")
    if not isinstance(music, dict) or not str(music.get("file", "")).strip():
        raise ValueError("publishing.music.file is required")
    cover = dict(publishing_spec.get("cover") or {})
    cover["file"] = "out/cover.png"
    publishing = {
        "version": 1,
        "series": "Chinese Wisdom in 60 Seconds",
        "platform_checked_on": publishing_spec.get("platform_checked_on"),
        "official_platform_sources": publishing_spec.get("official_platform_sources") or [],
        "tiktok": publishing_spec.get("tiktok") or {},
        "youtube_shorts": publishing_spec.get("youtube_shorts") or {},
        "source_note": publishing_spec.get("source_note"),
        "music_credit": publishing_spec.get("music_credit"),
        "music": {"file": str(music["file"]), "volume": float(music.get("volume", 0.05))},
        "cover": cover,
    }
    return story, audio, publishing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--check", action="store_true", help="validate the spec without writing manifests")
    args = parser.parse_args()
    root = args.project_dir.expanduser().resolve()
    spec = load_json(root / "episode-spec.json")
    story, audio, publishing = compile_spec(spec)
    if args.check:
        print(f"OK: episode spec valid - 6 scenes - {len(audio['segments'])} utterances")
        return
    write_json(root / "storyboard.json", story)
    write_json(root / "audio-manifest.json", audio)
    write_json(root / "publishing.json", publishing)
    print(f"OK: compiled episode spec - 6 scenes - {len(audio['segments'])} utterances - {root}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
