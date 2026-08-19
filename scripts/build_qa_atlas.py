#!/usr/bin/env python3
"""Build three bounded QA atlases from source art, final frames, motion samples, and cover."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


PAPER = (247, 240, 222)
INK = (47, 51, 56)
FRAME = (176, 164, 139)
SCENE_SIZE = (270, 480)


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def open_rgb(path: Path) -> Image.Image:
    try:
        return Image.open(path).convert("RGB")
    except FileNotFoundError as exc:
        raise ValueError(f"missing image: {path}") from exc


def labeled_cell(image: Image.Image, label: str, size: tuple[int, int]) -> Image.Image:
    cell = Image.new("RGB", (size[0] + 8, size[1] + 34), PAPER)
    fitted = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
    x = (cell.width - fitted.width) // 2
    cell.paste(fitted, (x, 28))
    draw = ImageDraw.Draw(cell)
    draw.text((6, 7), label, fill=INK)
    draw.rectangle((x - 1, 27, x + fitted.width, 28 + fitted.height), outline=FRAME, width=2)
    return cell


def grid(cells: list[Image.Image], columns: int, gap: int = 18) -> Image.Image:
    if not cells:
        raise ValueError("atlas requires at least one cell")
    rows = (len(cells) + columns - 1) // columns
    column_widths = [
        max((cell.width for index, cell in enumerate(cells) if index % columns == column), default=0)
        for column in range(columns)
    ]
    row_heights = [
        max(cell.height for cell in cells[row * columns : (row + 1) * columns])
        for row in range(rows)
    ]
    canvas = Image.new(
        "RGB",
        (sum(column_widths) + (columns + 1) * gap, sum(row_heights) + (rows + 1) * gap),
        PAPER,
    )
    x_offsets = [gap]
    for width in column_widths[:-1]:
        x_offsets.append(x_offsets[-1] + width + gap)
    y_offsets = [gap]
    for height in row_heights[:-1]:
        y_offsets.append(y_offsets[-1] + height + gap)
    for index, cell in enumerate(cells):
        column = index % columns
        row = index // columns
        x = x_offsets[column] + (column_widths[column] - cell.width) // 2
        y = y_offsets[row]
        canvas.paste(cell, (x, y))
    return canvas


def normalized_crop(image: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    left, top, right, bottom = box
    return image.crop(
        (
            round(left * image.width),
            round(top * image.height),
            round(right * image.width),
            round(bottom * image.height),
        )
    )


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--scene-frame", action="append")
    parser.add_argument("--source-frame", action="append")
    parser.add_argument("--source-only", action="store_true", help="build the pre-assembly source-art contact sheet only")
    parser.add_argument(
        "--motion-frame",
        action="append",
        help="optional LABEL=PATH sample; pass start/mid/end frames for moving scenes",
    )
    parser.add_argument("--cover", default="out/cover.png")
    args = parser.parse_args()

    root = args.project_dir.expanduser().resolve()
    if not args.source_only and len(args.scene_frame or []) != 6:
        raise ValueError("provide exactly six --scene-frame arguments in scene order")
    if args.source_frame and len(args.source_frame) != 6:
        raise ValueError("when used, provide exactly six --source-frame arguments in scene order")
    story_path = root / "storyboard.json"
    try:
        story = json.loads(story_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid or missing storyboard.json: {exc}") from exc
    scenes = story.get("scenes", [])
    if len(scenes) != 6:
        raise ValueError("storyboard.json must contain six scenes")

    sources = [open_rgb(resolve(root, item)) for item in args.source_frame or []]
    cover = open_rgb(resolve(root, args.cover))
    qa = root / "qa"

    if args.source_only:
        if len(sources) != 6:
            raise ValueError("--source-only requires exactly six --source-frame arguments")
        source_cells = [
            labeled_cell(source, f"{scene.get('id', index + 1)} {scene.get('narrative_function', '')} source", SCENE_SIZE)
            for index, (scene, source) in enumerate(zip(scenes, sources))
        ]
        source_cells.append(labeled_cell(cover, "cover art", SCENE_SIZE))
        path = qa / "source-art-contact-sheet.png"
        save(grid(source_cells, columns=4), path)
        print(f"OK: source-art QA atlas - {path}")
        return

    frames = [open_rgb(resolve(root, item)) for item in args.scene_frame]

    contact_cells = []
    for index, (scene, frame) in enumerate(zip(scenes, frames)):
        label = f"{scene.get('id', index + 1)} {scene.get('narrative_function', '')}"
        if sources:
            contact_cells.append(labeled_cell(sources[index], f"{label} source", SCENE_SIZE))
        contact_cells.append(labeled_cell(frame, f"{label} final", SCENE_SIZE))
    for value in args.motion_frame or []:
        if "=" not in value:
            raise ValueError("--motion-frame must use LABEL=PATH")
        label, path = value.split("=", 1)
        if not label.strip() or not path.strip():
            raise ValueError("--motion-frame must use non-empty LABEL=PATH")
        contact_cells.append(labeled_cell(open_rgb(resolve(root, path)), f"motion {label.strip()}", SCENE_SIZE))
    contact_cells.append(labeled_cell(cover, "cover", SCENE_SIZE))
    save(grid(contact_cells, columns=4), qa / "story-contact-sheet.png")

    detail_cells: list[Image.Image] = []
    for scene, frame in zip(scenes, frames):
        scene_id = str(scene.get("id", "?"))
        caption = normalized_crop(frame, (0.0, 0.55, 1.0, 0.88))
        detail_cells.append(labeled_cell(caption, f"{scene_id} lower caption", (1080, 634)))
        bubble = scene.get("bubble")
        if isinstance(bubble, dict):
            x = float(bubble.get("x", 0.1))
            y = float(bubble.get("y", 0.1))
            width = float(bubble.get("width", 0.4))
            detail_cells.append(
                labeled_cell(
                    normalized_crop(
                        frame,
                        (max(0.0, x - 0.06), max(0.0, y - 0.06), min(1.0, x + width + 0.06), min(1.0, y + 0.30)),
                    ),
                    f"{scene_id} bubble",
                    (1080, 634),
                )
            )
    meaning = normalized_crop(frames[5], (0.08, 0.08, 0.85, 0.82))
    detail_cells.append(labeled_cell(meaning, "06 meaning card", (1080, 1421)))
    save(grid(detail_cells, columns=2), qa / "text-detail-atlas.png")

    cover_cells = [
        labeled_cell(cover, "vertical", (540, 960)),
        labeled_cell(ImageOps.fit(cover, (1080, 1080), centering=(0.5, 0.43)), "square crop", (1080, 1080)),
        labeled_cell(ImageOps.fit(cover, (1080, 608), centering=(0.5, 0.43)), "horizontal crop", (1080, 608)),
    ]
    save(grid(cover_cells, columns=2), qa / "cover-crops.png")

    print(f"OK: QA atlases - {qa / 'story-contact-sheet.png'} - {qa / 'text-detail-atlas.png'} - {qa / 'cover-crops.png'}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
