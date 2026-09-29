"""Structured audit logger for the prompt firewall."""

from __future__ import annotations

import json
import time
from pathlib import Path

AUDIT_FILE = Path.home() / ".config" / "agentic-store" / "firewall_audit.jsonl"


def log_event(
    event: str, detail: str, findings: list[dict] | None = None, safe: bool = True
) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        "detail": detail,
        "safe": safe,
        "findings": findings or [],
    }
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_logs(
    limit: int = 100, show_originals: bool = False, event_filter: str = "all"
) -> list[dict]:
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    if event_filter == "errors":
        entries = [
            e
            for e in entries
            if e.get("event") == "blocked"
            or "error" in e.get("event", "")
            or e.get("safe") is False
        ]
    elif event_filter == "sanitized":
        entries = [e for e in entries if e.get("event") == "redacted"]
    if not show_originals:
        for entry in entries:
            entry["findings"] = [
                {k: v for k, v in f.items() if k != "original"}
                for f in entry.get("findings", [])
            ]
    return list(reversed(entries[-max(1, min(limit, 1000)) :]))


def clear_logs() -> None:
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()
