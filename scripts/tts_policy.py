"""Shared MiMo voice and fallback policy."""

from __future__ import annotations

import os
from typing import Any


DEFAULT_MIMO_VOICES = (
    "mimo_default",
    "冰糖",
    "茉莉",
    "苏打",
    "白桦",
    "Mia",
    "Chloe",
    "Milo",
    "Dean",
)


def allowed_mimo_voices() -> tuple[str, ...]:
    """Return the deployment-specific allowlist, or the verified public defaults."""
    configured = os.environ.get("MIMO_ALLOWED_VOICES", "")
    if configured.strip():
        voices = tuple(item.strip() for item in configured.split(",") if item.strip())
        if voices:
            return voices
    return DEFAULT_MIMO_VOICES


def validate_manifest_voice_ids(manifest: dict[str, Any]) -> list[str]:
    allowed = set(allowed_mimo_voices())
    errors: list[str] = []
    voices = manifest.get("voices")
    if not isinstance(voices, dict):
        return errors
    for speaker, profile in voices.items():
        if not isinstance(profile, dict):
            continue
        voice_id = str(profile.get("mimo_voice", "")).strip()
        if voice_id and voice_id not in allowed:
            errors.append(
                f"voice profile {speaker!r}.mimo_voice {voice_id!r} is unsupported; "
                f"allowed voices: {', '.join(allowed_mimo_voices())}"
            )
    return errors
