# Project data contract

For a new episode, author only `episode-spec.json`. Do not hand-edit the generated `storyboard.json`, `audio-manifest.json`, `publishing.json`, or `src/index.jsx`.

## Compact source of truth

- `episode-spec.json`: idiom, pinyin, meaning card, characters, sources, six scenes, utterances, caption pages, visual focus, motion, the fixed scene-02 copyright mark, optional bubble/layout overrides, publishing copy, music, and cover.
- `storyboard.json`, `audio-manifest.json`, `publishing.json`: deterministic compiled contracts for validators and runtime.
- `audio-result.json`: actual provider, paths, measured durations, and fallback evidence.
- `src/index.jsx`: immutable data-driven renderer bundled with the skill.

After changing `episode-spec.json`, compile and validate content before generating assets:

```bash
python scripts/compile_episode.py --project-dir <episode>
python scripts/validate_project.py --phase content --project-dir <episode> --workspace-dir <workspace>
```

Run full validation only after current platform data and publishing fields are complete:

```bash
python scripts/validate_project.py --project-dir <episode> --workspace-dir <workspace>
```

## Authoring rules

Keep six scene functions in this order: `hook → setup → cause → turn → consequence → meaning`. The compiler supplies IDs, fixed runtime fields, MiMo/Edge policy, and the three meaning utterances; never repeat those fields in the spec.

For narration, split exact spoken text into `caption_pages`. Each page may contain at most two lines. Across all pages, text must equal the spoken utterance apart from whitespace and line breaks. Dialogue uses one utterance plus one normalized `bubble` object on its scene.

Use normalized coordinates for focus and bubbles. Use exactly 2–3 single-direction motion definitions. Put per-episode caption, meaning-card, and cover geometry in the optional layout objects rather than editing JSX.

Version 2 episodes must preserve `copyright_mark` only on scene 02 as `© CARTGO` at `x: 120`, `y: 210`, `font_size: 36`, and `opacity: 0.55`. Keep it visible for the full scene. Version 1 episodes remain valid without this mark.

Generate YouTube Markdown only from the compiled `publishing.json`:

```bash
python scripts/youtube_publishing.py --project-dir <episode>
```
