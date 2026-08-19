# MiMo audio policy

## Provider order

Use Xiaomi MiMo `mimo-v2.5-tts` first. Read its credential only from `MIMO_API_KEY`; never write credentials to a project, skill, log, or message. Use `MIMO_BASE_URL` only for a configured compatible endpoint.

Verified default voice IDs include `mimo_default`, `Mia`, `Chloe`, `Milo`, and `Dean`. Validate every configured `mimo_voice`; never invent a voice ID from prose.

Treat invalid voice IDs, unavailable models, and invalid request parameters as configuration failures that must be fixed. Do not route configuration failures to Edge.

Treat a missing credential, authentication or quota failure, repeated timeout/rate-limit/server error, or empty/invalid returned audio as provider unavailability. These conditions may use whole-video Edge fallback only after explicit approval.

## Whole-video fallback

Default to strict MiMo. Retry transient service failures twice. Use `--allow-edge-fallback` only after explicit user approval. If approved fallback is needed, discard the incomplete MiMo batch and regenerate every utterance with `edge-tts`. Record requested provider, actual provider, approval, and reason in `audio-result.json`. Never mix providers.

## Timing and quality

- Use the shared workspace cache at `<workspace>/.cache/tts`; do not create an episode-local `tts-cache`. Keep disposable synthesis output outside the episode.
- Synthesize one utterance per segment and write the `ffprobe`-measured `duration_sec` into every `audio-result.json` segment.
- Preserve pause metadata when recalculating scene timing.
- In the meaning scene, synthesize three ordered utterances: the exact Chinese idiom with a native Mandarin profile, the exact English meaning with a native English profile, and the English reflection question with that English profile.
- Leave `400–600 ms` after the spoken Chinese idiom before the English meaning.
- Keep the tone-marked pinyin and source citation visible but unspoken unless the user explicitly requests otherwise. Do not create audio segments for either field.
- Review the Chinese idiom tones and the English pronunciation independently.
- Normalize speech consistently, duck background music, output stereo AAC at 48 kHz, and keep true peak at or below `-1.2 dBTP`.
- Retain the music license evidence and SHA-256. Preserve a music-free speech stem when practical.

Write the synthesis result directly to the canonical project root so the renderer and delivery validator use it without a copy or repair step:

```bash
python scripts/synthesize_audio.py --manifest <episode>/audio-manifest.json --output-dir <episode>/public/audio --result-path <episode>/audio-result.json --cache-dir <workspace>/.cache/tts
```
