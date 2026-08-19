# Layout, motion, and visual revision policy

Apply [visual-style.md](visual-style.md). Keep generated art text-free, reserve negative space near speakers, and composite all text in Remotion.

## Motion

- Animate exactly 2–3 scenes; prefer hook, turn, and consequence.
- Give each moving scene one clearly perceptible, single-direction motion: scale `1.00` to `1.04–1.06` or pan `24–36 px`; default to `1.05` or `30 px`.
- Never combine noticeable pan and scale or use reversal, loop, pulse, breathing, oscillation, shake, or repeated zoom.
- Keep other scenes static. Caption, bubble, and meaning-card reveals do not count as moving scenes. Use `6–10` frame cuts or dissolves.
- Preview the start, midpoint, and end of each moving scene at phone size. Preserve the paper edge throughout.

## Captions and bubbles

- Make captions exactly match spoken English and use no more than two lines. For the standard `1080x1920` layout, set the narration-caption container to `bottom={210}`. It must remain in the lower paper margin without covering faces, gestures, or props; if the artwork does not provide sufficient clear paper there, revise the artwork or use a scene-specific position that preserves those constraints.
- Center every centered container geometrically at `x = 540 ± 1 px`. Use `CenteredBlock`; `textAlign: 'center'` alone is insufficient.
- Place each dialogue bubble near its speaker with a short, physically attached, unambiguous tail. Do not duplicate dialogue as both bubble and bottom caption unless accessibility requires it.
- If artwork clearance conflicts with platform UI clearance, render the keyframe for user confirmation; do not silently shrink or restyle text.

## Copyright mark

- In version 2 episodes, keep `© CARTGO` visible for the full duration of scene 02 only.
- Place it at `x: 120`, `y: 210` with `36 px` type and `0.55` opacity. Do not show it in scenes 01 or 03–06, or on the cover.
- Preserve its text, position, size, opacity, and duration during revisions. Confirm it in the scene-02 final keyframe at full resolution and phone size.

## Revisions and QA

For a position-only revision, preserve width, height, font size, line height, padding, color, content, and animation. Compare those values with the prior version. Render affected full-resolution keyframes and inspect at phone size before a full render.

Use `build_qa_atlas.py` for a bounded visual pass. Before assembly, inspect exactly one source-art contact sheet. After assembly, inspect exactly the three final atlases; include start/mid/end samples for each moving scene in the story contact sheet. Open an individual frame only when an atlas indicates a possible defect. After a repair, rerender and inspect only affected frames before rebuilding the final atlases once.

Pre-assembly call: pass `--source-only`, six ordered `--source-frame` values, and `--cover public/images/cover-art.png`. Final call: pass six ordered `--scene-frame` values, `--cover out/cover.png`, and each motion sample as `--motion-frame LABEL=PATH`. The script emits the fixed atlas filenames; do not create parallel QA sets.
