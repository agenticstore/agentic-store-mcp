"""Persist firewall configuration and user-defined rules."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".config" / "agentic-store" / "firewall_config.json"

DEFAULT_CONFIG: dict = {
    "enabled": False,
    "port": 8766,
    "deterministic": {
        "pii": True,
        "secrets": True,
        "file_paths": True,
        "ip_addresses": True,
    },
    "llm": {
        "enabled": False,
        "model": None,
        "custom_rules": [],
    },
    "mode": "redact",
    "recording": False,
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        if "deterministic" in data:
            merged["deterministic"] = {**DEFAULT_CONFIG["deterministic"], **data["deterministic"]}
        if "llm" in data:
            merged["llm"] = {**DEFAULT_CONFIG["llm"], **data["llm"]}
        return merged
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
