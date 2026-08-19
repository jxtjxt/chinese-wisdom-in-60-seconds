---
name: chinese-wisdom-in-60-seconds
description: Research, create, validate, or narrowly revise one English-first 9:16 animated short (normally 50–65 seconds) explaining a Chinese idiom, proverb, historical allusion, or compact classical story for TikTok, YouTube Shorts, or Reels. Use for sourced story adaptation, English scripts, pinyin meaning cards, cartoon illustrations, MiMo voices, captions, bubbles, covers, music, publishing metadata, Remotion rendering, delivery QA, and revisions to any of those artifacts.
---

# Chinese Wisdom in 60 Seconds

Produce one polished `1080x1920`, 30 fps short and one dedicated cover. Preserve source traceability, `sunlit-storybook-9x16`, bilingual meaning-card behavior, MiMo-first audio, and the delivery contract. Never publish without explicit permission.

## Token-bounded operation

- Load each policy only when its phase begins; never preload all policies.
- New episode: edit only `episode-spec.json`, then compile. Never hand-edit generated manifests or canonical `src/index.jsx`.
- Do not read generated manifests, renderer code, successful logs, or unchanged artifacts unless an error implicates them.
- Batch inspections, validators, still renders, and fixes. Use `scripts/run_quiet.py` for verbose commands and read only a failure tail.
- Use only the prescribed QA passes. Open a single frame only when an atlas shows a possible defect.

For a narrow revision, load only its implicated policy and preserve every unrequested property. Legacy episodes without `episode-spec.json` keep their existing manifests and renderer.

## New-episode phases

### 0. Initialize

```bash
python scripts/init_episode.py --workspace-dir <workspace> --slug <slug> --idiom <idiom>
```

Read [storage-runtime-policy.md](references/storage-runtime-policy.md) only if initialization, dependency, cache, render, or retention work requires it.

### 1. Story and data

Read [story-policy.md](references/story-policy.md) and [project-schema.md](references/project-schema.md). Research one primary text or authoritative edition with targeted passage extraction. Write six causal beats `hook → setup → cause → turn → consequence → meaning`, utterances, caption pages, sources, and visual descriptions in `episode-spec.json`.

```bash
python scripts/compile_episode.py --project-dir <episode>
python scripts/validate_project.py --phase content --project-dir <episode> --workspace-dir <workspace>
```

Do not generate assets until this passes.

### 2. Illustrations

Read [visual-style.md](references/visual-style.md) and [visual-audio-policy.md](references/visual-audio-policy.md). With `imagegen`, generate exactly six text-free scenes and one text-free cover. Reuse one concise character/style lock; vary scene action, composition, focus, and reserved text space. Regenerate only failures. Build and inspect the one prescribed source-art atlas.

### 3. Audio

Read [audio-policy.md](references/audio-policy.md). Synthesize once after script lock:

```bash
python scripts/synthesize_audio.py --manifest <episode>/audio-manifest.json --output-dir <episode>/public/audio --result-path <episode>/audio-result.json --cache-dir <workspace>/.cache/tts
```

Review Chinese tones and English pronunciation. For text changes, edit the spec, recompile, and regenerate only changed utterances; fallback remains whole-video only.

### 4. Render and QA

Use the canonical renderer without reading or editing it. First render affected full-resolution keyframes and start/mid/end for each of the 2–3 moving scenes. Fix issues together in the spec, compile once, and rerender affected frames. Render the full H.264/AAC video only after keyframes pass; compress strictly below `10,000,000` bytes without reducing resolution unless approved.

For version 2 episodes, preserve the fixed `© CARTGO` mark throughout scene 02 only and verify it at full resolution and phone size.

Build exactly three final atlases with `build_qa_atlas.py`, including six final frames, cover, and labeled motion samples. Inspect at original detail and phone size. After a repair, inspect affected frames and rebuild the final atlases once.

### 5. Publishing and delivery

Read [platform-policy.md](references/platform-policy.md), then check cached verification:

```bash
python scripts/platform_cache.py --workspace-dir <workspace> status
```

Reuse a `HIT`. On `MISS`, verify official TikTok and YouTube sources once and record them with `platform_cache.py ... record`. Complete publishing fields in the spec, then run:

```bash
python scripts/compile_episode.py --project-dir <episode>
python scripts/validate_project.py --project-dir <episode> --workspace-dir <workspace>
python scripts/youtube_publishing.py --project-dir <episode>
python scripts/validate_delivery.py --project-dir <episode> --workspace-dir <workspace>
```

Apply retention rules only after delivery validation passes.

## Revision and delivery

For a position-only revision, preserve size, typography, padding, color, content, and animation; change only its spec layout override, inspect affected keyframes, then render once.

Deliver the MP4, cover, YouTube Markdown, spec, compiled manifests, `audio-result.json`, retained evidence, and canonical assets. Report idiom, pinyin, duration, dimensions, scene/moving-scene counts, narration language, actual TTS, music license, platform-check date, MP4 bytes, and output paths.
