# TikTok and YouTube Shorts policy

Platform rules change. Before finalizing an episode, check current official TikTok and YouTube documentation and record URLs and the verification date in `publishing.json`.

Run `scripts/platform_cache.py --workspace-dir <workspace> status` first. A valid `HIT` is an already verified check within the validator's seven-day window and may be reused without browsing. On `MISS`, verify both official platforms once, record the cache, and copy its date and URLs into `episode-spec.json`.

## Universal master

- Use `1080x1920`, portrait `9:16`, 30 fps, normally 50–65 seconds.
- Keep essential action and text in the conservative central safe region. Treat the right edge and lowest band as platform UI territory.
- Preview on a phone-sized frame.

## Text layout

- Use no more than two narration-caption lines and place them in the lower safe region, below central action but above bottom UI.
- Keep text away from right-side controls. Use sentence case, high contrast, and a solid or softly opaque backing.
- Place speech bubbles close to their speaker. Tails must be short, attached, unambiguous, and clear of faces and key props.
- Do not duplicate dialogue as both a bubble and a bottom caption unless accessibility requires it.

## Dedicated cover

- Create `out/cover.png` at `1080x1920`; do not use a random frame.
- Use one strong, truthful visual contradiction or reversal and an English-first hook of 3–6 words. The Chinese idiom may appear smaller.
- Keep faces and title inside a central crop-safe region. Test vertical, square, and horizontal crop previews plus phone-size legibility.
- Keep the cover's characters and cartoon abstraction consistent with the episode. Reject misleading clickbait and tiny text.
- Record `cover.title`, `cover.visual_hook`, and `cover.selection_reason` in `publishing.json`.

## Publishing copy

- Provide distinct TikTok and YouTube Shorts copy for the same master.
- Use a short accurate English title, translated description with idiom, pinyin, meaning and source, and a few focused hashtags. Keep YouTube Studio backend Tags in `youtube_shorts.tags` without `#`; do not confuse them with description hashtags.
- Preserve a clean audio master; platform-native music is a separate publication decision.
