# Shared runtime and storage policy

Use one versioned workspace for all episodes. Default to `CHINESE_WISDOM_WORKSPACE` when set; otherwise use `~/CodexWorkspaces/chinese-wisdom-v1`.

## Workspace layout

```text
chinese-wisdom-v1/
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── node_modules/          # one shared Remotion installation
├── .venv/                 # optional shared Python environment only
├── .cache/
│   ├── tts/               # content-addressed cache shared by episodes
│   └── renders/           # reproducible masters and two-pass logs
└── episodes/
    └── episode-slug/
        ├── storyboard.json
        ├── audio-manifest.json
        ├── publishing.json
        ├── audio-result.json
        ├── src/
        ├── public/        # canonical images, audio, music, and cover art
        ├── evidence/
        ├── qa/
        └── out/              # MP4, cover, and YouTube publishing Markdown
```

Run `scripts/ensure_shared_workspace.py --workspace-dir <workspace>` before creating an episode. It installs exact Remotion dependencies only when the shared dependency fingerprint changes or `node_modules` is missing. Never run `pnpm install`, `npm install`, or `python -m venv` inside an episode.

New episodes use the canonical `src/index.jsx` copied by `init_episode.py`. Do not read or edit it during normal production. Express episode-specific text, timing, audio, motion, bubbles, and layout in `episode-spec.json`; inspect the renderer only when a render error specifically implicates canonical runtime code.

Render from the shared workspace so imports resolve through its `node_modules`:

```powershell
pnpm --dir <workspace> exec remotion render <episode>/src/index.jsx ChineseWisdomShort <episode>/out/chinese-wisdom-short.mp4 --public-dir <episode>/public --codec h264 --audio-codec aac --pixel-format yuv420p
pnpm --dir <workspace> exec remotion still <episode>/src/index.jsx Cover <episode>/out/cover.png --public-dir <episode>/public --frame 0
```

Use the configured Python runtime directly. If additional Python packages become necessary, create only `<workspace>/.venv` and reuse it for every episode.

## Canonical assets and caches

- Keep episode images only in `public/images`, speech only in `public/audio`, and music only in `public/music`. Do not duplicate them in top-level `images`, `audio`, or `music` directories.
- Use `<workspace>/.cache/tts` as `synthesize_audio.py --cache-dir`. Put disposable synthesis batches outside the episode, for example `<workspace>/.cache/tts-runs/<episode-slug>`.
- Put the temporary high-bitrate master and two-pass FFmpeg logs in `<workspace>/.cache/renders`, not in the episode. Remove that episode's render intermediates only after final delivery validation succeeds.
- Keep source evidence and final delivery files per episode; these are not shared dependencies.

## Post-validation retention

After delivery validation succeeds, retain the final MP4, cover, `out/youtube-publishing.md`, JSON manifests, canonical public assets, evidence, and final QA contact sheets. Remove only reproducible intermediates: the episode's high-bitrate master and two-pass logs from the shared render cache, plus render logs, temporary `.work` directories, and old `tts-output*` batches inside the episode. Never delete before successful final validation.

The episode directory must not contain `node_modules`, `.venv`, `tts-cache`, `package.json`, `pnpm-lock.yaml`, or `pnpm-workspace.yaml`.
