"""Prompt recording store — captures full outbound prompt text when enabled."""
from __future__ import annotations

import json
import time
from pathlib import Path

RECORDINGS_FILE = Path.home() / ".config" / "agentic-store" / "firewall_recordings.jsonl"


def record_prompt(
    provider: str,
    model: str,
    prompt_text: str,
    redacted: bool,
    findings_count: int,
) -> None:
    """Append one prompt recording entry."""
    RECORDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": provider,
        "model": model,
        "prompt": prompt_text,
        "redacted": redacted,
        "findings_count": findings_count,
        "char_count": len(prompt_text),
    }
    with open(RECORDINGS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_recordings(limit: int = 50) -> list[dict]:
    """Return most recent recordings, newest first."""
    if not RECORDINGS_FILE.exists():
        return []
    lines = RECORDINGS_FILE.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return list(reversed(entries[-limit:]))


def clear_recordings() -> None:
    if RECORDINGS_FILE.exists():
        RECORDINGS_FILE.unlink()


def recordings_size_kb() -> float:
    if not RECORDINGS_FILE.exists():
        return 0.0
    return round(RECORDINGS_FILE.stat().st_size / 1024, 1)
