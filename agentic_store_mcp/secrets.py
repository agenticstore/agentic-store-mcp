"""
secrets.py — generic token storage for AgenticStore MCP.

Resolution order for get_token(service):
  1. Environment variable  ({SERVICE.upper()}, {SERVICE.upper()}_TOKEN, {SERVICE.upper()}_KEY)
  2. OS keyring            (via `keyring` library)
  3. Config file fallback  (~/.config/agentic-store/tokens.json, mode 0o600)

set_token() always writes to the OS keyring (with config file fallback when keyring
is unavailable, e.g. headless/CI environments).

Service name convention: "{connector_slug}_{field_name}"
  e.g. "github_token", "openai_api_key", "anthropic_api_key"
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

# ─── Config file fallback ─────────────────────────────────────────────────────

_CONFIG_DIR = Path.home() / ".config" / "agentic-store"
_TOKENS_FILE = _CONFIG_DIR / "tokens.json"

KEYRING_SERVICE = "agentic-store-mcp"


def _read_config() -> dict[str, str]:
    try:
        return json.loads(_TOKENS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(data: dict[str, str]) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _TOKENS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _TOKENS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600


# ─── Keyring helpers ──────────────────────────────────────────────────────────

def _keyring_get(service: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, service)
    except Exception:
        return None


def _keyring_set(service: str, token: str) -> bool:
    """Returns True if keyring write succeeded, False if fallback needed."""
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, service, token)
        return True
    except Exception:
        return False


def _keyring_delete(service: str) -> bool:
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, service)
        return True
    except Exception:
        return False


# ─── Public API ───────────────────────────────────────────────────────────────

def get_token(service: str) -> str | None:
    """
    Retrieve a stored token for the given service name.

    Checks (in order):
      1. Environment variables: SERVICE, SERVICE_TOKEN, SERVICE_KEY (all uppercase)
      2. OS keyring
      3. Config file ~/.config/agentic-store/tokens.json

    Returns None if not found anywhere.
    """
    # 1. Environment variables
    upper = service.upper()
    for env_var in (upper, f"{upper}_TOKEN", f"{upper}_KEY"):
        val = os.environ.get(env_var)
        if val:
            return val

    # 2. OS keyring
    val = _keyring_get(service)
    if val:
        return val

    # 3. Config file
    return _read_config().get(service)


def set_token(service: str, token: str) -> None:
    """
    Store a token for the given service name.

    Writes to OS keyring first. Falls back to config file if keyring
    is unavailable (e.g. headless/CI environments). Config file is
    created with mode 0o600 (owner read/write only).
    """
    if not _keyring_set(service, token):
        data = _read_config()
        data[service] = token
        _write_config(data)


def remove_token(service: str) -> None:
    """Remove a stored token from keyring and config file."""
    _keyring_delete(service)
    data = _read_config()
    if service in data:
        del data[service]
        _write_config(data)


def list_tokens() -> list[str]:
    """
    Return service names that have tokens stored in the config file.
    Note: keyring-only tokens are not enumerable — only config file entries
    are returned. Service names only, never values.
    """
    return list(_read_config().keys())
