# Chinese Wisdom in 60 Seconds

A Codex skill for researching, producing, and validating one polished English-first vertical short about a Chinese idiom, proverb, historical allusion, or compact classical story.

The workflow produces a `1080x1920`, 30 fps video for TikTok, YouTube Shorts, or Reels, together with a dedicated cover, source evidence, publishing copy, and reviewable QA artifacts.

## What it does

- Grounds each story in a primary text or authoritative edition.
- Builds a six-beat narrative: hook, setup, cause, turn, consequence, and meaning.
- Uses six text-free storybook illustrations and one separate cover.
- Creates English-first narration with a bilingual Chinese–pinyin–English meaning card.
- Uses MiMo-first speech synthesis, captions, music evidence, and delivery checks.
- Renders H.264/AAC video and validates the final delivery package.
- Supports narrow revisions without changing unrelated creative decisions.

## Requirements

- Codex with the `imagegen` capability
- Python 3
- Node.js and pnpm
- FFmpeg and ffprobe
- MiMo TTS credentials for the default audio workflow

Keep credentials in environment variables or an external secret store. Never add them to an episode, this skill, or Git.

## Installation

Clone the repository into your Codex skills directory:

```bash
git clone https://github.com/jxtjxt/chinese-wisdom-in-60-seconds.git ~/.codex/skills/chinese-wisdom-in-60-seconds
```

Restart Codex if the skill is not discovered automatically.

## Usage

Ask Codex to use the skill with an idiom or story, for example:

```text
Use $chinese-wisdom-in-60-seconds to turn 熟能生巧 into an English 9:16 short video.
```

For a new episode, the workflow initializes a workspace project and treats `episode-spec.json` as the only hand-edited source of truth:

```bash
python scripts/init_episode.py --workspace-dir <workspace> --slug <slug> --idiom <idiom>
python scripts/compile_episode.py --project-dir <episode>
python scripts/validate_project.py --phase content --project-dir <episode> --workspace-dir <workspace>
```

The skill then guides illustration generation, audio synthesis, keyframe review, final rendering, platform metadata, and delivery validation. See [`SKILL.md`](SKILL.md) for the complete operating contract.

## Repository layout

```text
.
├── SKILL.md                   # Skill entry point and workflow
├── agents/openai.yaml         # Display metadata and default prompt
├── references/                # Story, visual, audio, runtime, and platform policies
├── scripts/                   # Initialization, compilation, synthesis, QA, and validators
└── assets/                    # Episode template and shared Remotion runtime
```

## Safety and publishing

The skill may prepare platform-ready files and metadata, but it must not publish a video without explicit user permission.

## License

No license has been added yet. Until one is provided, the repository remains publicly viewable but is not granted an open-source reuse license.
