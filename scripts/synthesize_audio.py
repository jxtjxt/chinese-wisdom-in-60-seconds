#!/usr/bin/env python3
"""Synthesize a whole project's speech with MiMo and whole-video Edge fallback."""

from __future__ import annotations

import argparse
import base64
import importlib.metadata
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from hashlib import sha256
from pathlib import Path
from typing import Any

from tts_policy import validate_manifest_voice_ids


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ConfigurationError(ProviderError):
    """A manifest or request defect that must never trigger provider fallback."""


def retryable_http_status(status: int) -> bool:
    return status in {408, 429} or 500 <= status <= 599


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing audio manifest: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in audio manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("audio manifest must be a JSON object")
    for key in ("tts", "voices", "segments"):
        if key not in value:
            raise ValueError(f"audio manifest is missing {key}")
    tts = value["tts"]
    if not isinstance(tts, dict):
        raise ValueError("audio manifest tts must be an object")
    if not isinstance(tts.get("primary"), dict):
        raise ValueError("audio manifest tts.primary must be an object")
    if not isinstance(tts.get("fallback"), dict):
        raise ValueError("audio manifest tts.fallback must be an object")
    if not isinstance(value["voices"], dict):
        raise ValueError("audio manifest voices must be an object")
    if not isinstance(value["segments"], list):
        raise ValueError("audio manifest segments must be an array")
    if tts.get("fallback_scope") != "whole_video":
        raise ValueError("only whole_video fallback is supported")
    return value


def endpoint_paths() -> tuple[str, str]:
    base = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base, base[: -len("/chat/completions")] + "/models"
    return base + "/chat/completions", base + "/models"


def request_json(request: urllib.request.Request, timeout: float = 45) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode("utf-8", errors="replace")
        error_type = ConfigurationError if exc.code in {400, 404, 422} else ProviderError
        raise error_type(
            f"MiMo HTTP {exc.code}: {body}",
            retryable=retryable_http_status(exc.code),
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"MiMo connection failed: {exc}", retryable=True) from exc
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProviderError("MiMo returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ProviderError("MiMo returned a non-object response")
    return value


def mimo_preflight(api_key: str, model: str) -> None:
    _, models_endpoint = endpoint_paths()
    request = urllib.request.Request(
        models_endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    response = request_json(request, timeout=20)
    model_ids = {
        str(item.get("id"))
        for item in response.get("data", [])
        if isinstance(item, dict)
    }
    if model not in model_ids:
        raise ConfigurationError(f"MiMo model is unavailable: {model}")


def validate_mimo_configuration(manifest: dict[str, Any]) -> None:
    errors = validate_manifest_voice_ids(manifest)
    if errors:
        raise ConfigurationError("; ".join(errors))


def synthesize_mimo(
    segment: dict[str, Any],
    voice: dict[str, Any],
    model: str,
    api_key: str,
    output: Path,
    retries: int,
) -> None:
    endpoint, _ = endpoint_paths()
    emotion = str(segment.get("emotion", "natural"))
    direction = f"{voice.get('style', 'Natural and clear')}. Current emotion: {emotion}. Read only the target text."
    target_text = str(segment.get("tts_text", segment["text"]))
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": direction},
            {"role": "assistant", "content": target_text},
        ],
        "audio": {"format": "wav", "voice": voice.get("mimo_voice", "mimo_default")},
    }
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(
            endpoint,
            data=encoded,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            response = request_json(request)
            audio_data = response["choices"][0]["message"]["audio"]["data"]
            raw = base64.b64decode(audio_data, validate=True)
            if len(raw) < 44 or raw[:4] != b"RIFF":
                raise ProviderError("MiMo returned empty or invalid WAV audio")
            output.write_bytes(raw)
            return
        except ProviderError as exc:
            last_error = exc
            if not exc.retryable or attempt >= retries:
                break
            time.sleep(min(4, 2**attempt))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            last_error = ProviderError(f"MiMo returned malformed audio data: {exc}")
            break
    raise ProviderError(f"MiMo synthesis failed for {segment['id']}: {last_error}")


def synthesize_edge(
    segment: dict[str, Any],
    voice: dict[str, Any],
    output: Path,
) -> None:
    if importlib.util.find_spec("edge_tts") is None:
        raise ProviderError("edge-tts is not installed; run: python -m pip install edge-tts")
    command = [
        sys.executable,
        "-m",
        "edge_tts",
        "--voice",
        str(voice.get("edge_voice", "en-US-JennyNeural")),
        "--text",
        str(segment.get("tts_text", segment["text"])),
        "--write-media",
        str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        message = (completed.stderr or completed.stdout).strip()[-500:]
        raise ProviderError(f"edge-tts failed for {segment['id']}: {message}")


def media_duration(path: Path) -> float:
    command = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ProviderError("ffprobe is required to measure synthesized audio") from exc
    except subprocess.CalledProcessError as exc:
        raise ProviderError(f"ffprobe failed for {path}: {exc.stderr.strip()}") from exc
    return round(float(completed.stdout.strip()), 3)


def safe_id(value: Any) -> str:
    original = str(value)
    cleaned = "".join(char if char.isalnum() or char in "-_" else "-" for char in original)
    stem = (cleaned.strip("-") or "segment")[:72]
    digest = sha256(original.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{digest}"


def provider_revision(provider: str) -> str:
    if provider == "mimo":
        endpoint, _ = endpoint_paths()
        parsed = urllib.parse.urlsplit(endpoint)
        host = parsed.hostname or ""
        if parsed.port is not None:
            host += f":{parsed.port}"
        return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    try:
        return f"edge-tts/{importlib.metadata.version('edge-tts')}"
    except importlib.metadata.PackageNotFoundError:
        return "edge-tts/unavailable"


def audio_cache_key(
    segment: dict[str, Any],
    voice: dict[str, Any],
    provider: str,
    model: str,
) -> str:
    voice_key = "mimo_voice" if provider == "mimo" else "edge_voice"
    payload = {
        "version": 1,
        "provider": provider,
        "provider_revision": provider_revision(provider),
        "model": model if provider == "mimo" else "edge-tts",
        "voice": str(voice.get(voice_key, "")),
        "style": str(voice.get("style", "")),
        "emotion": str(segment.get("emotion", "natural")),
        "text": str(segment.get("tts_text", segment.get("text", ""))),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def cache_file(
    cache_dir: Path | None,
    provider: str,
    cache_key: str,
) -> Path | None:
    if cache_dir is None:
        return None
    extension = ".wav" if provider == "mimo" else ".mp3"
    return cache_dir / provider / f"{cache_key}{extension}"


def valid_cached_audio(path: Path | None, provider: str) -> bool:
    if path is None or not path.is_file():
        return False
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if provider == "mimo":
        return len(data) >= 44 and data[:4] == b"RIFF"
    return len(data) >= 128


def batch_fully_cached(
    manifest: dict[str, Any],
    provider: str,
    cache_dir: Path | None,
) -> bool:
    if cache_dir is None:
        return False
    voices = manifest["voices"]
    model = str(manifest["tts"]["primary"].get("model", "mimo-v2.5-tts"))
    for segment in manifest["segments"]:
        voice = voices.get(str(segment.get("speaker", "")))
        if not isinstance(voice, dict):
            return False
        key = audio_cache_key(segment, voice, provider, model)
        if not valid_cached_audio(cache_file(cache_dir, provider, key), provider):
            return False
    return True


def commit_audio_cache(records: list[dict[str, Any]]) -> None:
    for record in records:
        raw_target = record.pop("_cache_target", None)
        if not raw_target:
            continue
        target = Path(str(raw_target))
        source = Path(str(record["path"]))
        temporary: Path | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix=".tts-cache-", suffix=target.suffix, dir=target.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        except OSError:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def synthesize_batch(
    manifest: dict[str, Any],
    provider: str,
    target: Path,
    api_key: str | None,
    cache_dir: Path | None = None,
) -> list[dict[str, Any]]:
    voices = manifest["voices"]
    tts = manifest["tts"]
    retries = int(tts.get("max_retries", 2))
    model = str(tts["primary"].get("model", "mimo-v2.5-tts"))
    target.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for segment in manifest["segments"]:
        speaker = str(segment["speaker"])
        if speaker not in voices:
            raise ValueError(f"missing voice profile for {speaker}")
        extension = ".wav" if provider == "mimo" else ".mp3"
        output = target / f"{safe_id(segment['id'])}{extension}"
        input_hash = audio_cache_key(segment, voices[speaker], provider, model)
        cached = cache_file(cache_dir, provider, input_hash)
        cache_hit = valid_cached_audio(cached, provider)
        if cache_hit:
            assert cached is not None
            shutil.copy2(cached, output)
        elif provider == "mimo":
            if not api_key:
                raise ProviderError("MIMO_API_KEY is not set")
            synthesize_mimo(segment, voices[speaker], model, api_key, output, retries)
        else:
            synthesize_edge(segment, voices[speaker], output)
        digest = sha256(output.read_bytes()).hexdigest()[:16]
        records.append(
            {
                "id": segment["id"],
                "scene_id": segment["scene_id"],
                "speaker": speaker,
                "kind": segment["kind"],
                "language": segment.get("language"),
                "spoken_role": segment.get("spoken_role"),
                "text": segment["text"],
                "emotion": segment.get("emotion"),
                "pause_after_ms": int(segment.get("pause_after_ms", 0)),
                "path": str(output.resolve()),
                "duration_sec": media_duration(output),
                "sha256": digest,
                "input_hash": input_hash,
                "cache_hit": cache_hit,
            }
        )
        if not cache_hit and cached is not None:
            records[-1]["_cache_target"] = str(cached)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--result-path",
        type=Path,
        help="write audio-result.json here; defaults to <output-dir>/audio-result.json",
    )
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument(
        "--allow-edge-fallback",
        action="store_true",
        help="allow whole-video Edge fallback after a genuine MiMo service failure",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    result_path = args.result_path.expanduser().resolve() if args.result_path else output_dir / "audio-result.json"
    cache_dir = args.cache_dir.expanduser().resolve() if args.cache_dir else None
    try:
        manifest = load_manifest(manifest_path)
        validate_mimo_configuration(manifest)
    except (OSError, ValueError, ConfigurationError) as exc:
        raise SystemExit(f"ERROR: {exc}") from None
    if args.dry_run:
        print(
            f"OK: audio plan valid - {len(manifest['segments'])} segments - "
            "strict MiMo primary - Edge fallback requires explicit approval"
        )
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    api_key = os.environ.get("MIMO_API_KEY")
    fallback_reason: str | None = None
    actual_provider = "mimo"
    staging_parent = output_dir.parent
    staging = Path(tempfile.mkdtemp(prefix=".motion-comic-tts-", dir=staging_parent))
    try:
        try:
            model = str(manifest["tts"]["primary"].get("model", "mimo-v2.5-tts"))
            if not batch_fully_cached(manifest, "mimo", cache_dir):
                if not api_key:
                    raise ProviderError("MIMO_API_KEY is not set")
                mimo_preflight(api_key, model)
            records = synthesize_batch(
                manifest, "mimo", staging / "mimo", api_key, cache_dir
            )
            commit_audio_cache(records)
        except ConfigurationError as exc:
            raise SystemExit(
                "ERROR: invalid MiMo configuration; Edge fallback is forbidden: "
                f"{exc}"
            ) from None
        except ProviderError as exc:
            if not args.allow_edge_fallback:
                raise SystemExit(
                    "ERROR: MiMo unavailable and Edge fallback was not explicitly approved: "
                    f"{exc}"
                ) from None
            actual_provider = "edge-tts"
            fallback_reason = str(exc)
            shutil.rmtree(staging, ignore_errors=True)
            staging = Path(tempfile.mkdtemp(prefix=".motion-comic-tts-", dir=staging_parent))
            records = synthesize_batch(
                manifest, "edge-tts", staging / "edge", None, cache_dir
            )
            commit_audio_cache(records)

        final_media = output_dir / actual_provider
        final_media.mkdir(parents=True, exist_ok=True)
        for record in records:
            source = Path(record["path"])
            target = final_media / source.name
            shutil.copy2(source, target)
            record["path"] = str(target.resolve())
        result = {
            "version": 1,
            "requested_tts": "mimo-v2.5-tts",
            "actual_tts": actual_provider,
            "fallback_used": actual_provider != "mimo",
            "fallback_approved": bool(args.allow_edge_fallback and actual_provider != "mimo"),
            "fallback_reason": fallback_reason,
            "cache_hits": sum(bool(record.get("cache_hit")) for record in records),
            "segments": records,
        }
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: synthesized {len(records)} segments with {actual_provider} -> {result_path}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
