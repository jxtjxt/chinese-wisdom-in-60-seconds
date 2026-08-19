import argparse
import json
from pathlib import Path


OUTPUT_NAME = "youtube-publishing.md"


def load_publishing(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc


def validate_publishing_copy(publishing):
    errors = []
    youtube = publishing.get("youtube_shorts")
    if not isinstance(youtube, dict):
        return ["publishing.youtube_shorts is required"]

    title = youtube.get("title")
    description = youtube.get("description")
    if not isinstance(title, str) or not title.strip():
        errors.append("publishing.youtube_shorts.title is required")
    elif "\n" in title or "\r" in title:
        errors.append("publishing.youtube_shorts.title must be one line")
    if not isinstance(description, str) or not description.strip():
        errors.append("publishing.youtube_shorts.description is required")

    hashtags = youtube.get("hashtags")
    if not isinstance(hashtags, list) or not hashtags:
        errors.append("publishing.youtube_shorts.hashtags must be a non-empty list")
    elif any(
        not isinstance(item, str)
        or not item.startswith("#")
        or any(char.isspace() for char in item)
        for item in hashtags
    ):
        errors.append("publishing.youtube_shorts.hashtags must be non-empty #Hashtags without spaces")

    tags = youtube.get("tags")
    if not isinstance(tags, list) or not tags:
        errors.append("publishing.youtube_shorts.tags must be a non-empty list")
    else:
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                errors.append("publishing.youtube_shorts.tags must contain non-empty strings")
                break
            if tag.startswith("#"):
                errors.append("publishing.youtube_shorts.tags are YouTube Studio Tags and must not start with #")
                break
            if "," in tag:
                errors.append("publishing.youtube_shorts.tags entries must not contain commas")
                break
    return errors


def render_markdown(publishing):
    errors = validate_publishing_copy(publishing)
    if errors:
        raise ValueError("; ".join(errors))
    youtube = publishing["youtube_shorts"]
    description = youtube["description"].strip()
    hashtags = " ".join(item.strip() for item in youtube["hashtags"])
    tags = ", ".join(item.strip() for item in youtube["tags"])
    return (
        "# YouTube Publishing Copy\n\n"
        "## 1. Title\n\n"
        f"{youtube['title'].strip()}\n\n"
        "## 2. Description\n\n"
        f"{description}\n\n"
        f"{hashtags}\n\n"
        "## 3. Tags\n\n"
        f"{tags}\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    args = parser.parse_args()
    root = Path(args.project_dir).resolve()
    try:
        publishing = load_publishing(root / "publishing.json")
        markdown = render_markdown(publishing)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from None
    output = root / "out" / OUTPUT_NAME
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8", newline="\n")
    print(f"OK: generated {output}")


if __name__ == "__main__":
    main()
