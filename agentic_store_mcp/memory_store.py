"""
memory_store.py — shared storage layer for the AgenticStore memory system.

Storage layout:
  ~/.config/agentic-store/memory/
  ├── facts.json          ← {key: {key, value, category, created_at, updated_at}}
  ├── session.jsonl       ← append-only log, one JSON object per line
  ├── strategy.md         ← free-form markdown
  └── checkpoints/
      ├── checkpoint_20260309T142300.json
      └── {user-name}.json

Design:
  - MEMORY_DIR is created on first write, never on import
  - facts.json writes use fcntl.flock (POSIX) for safety; falls back gracefully on Windows
  - JSONL append is atomic for lines < 4096B (POSIX write guarantee)
  - "latest" checkpoint = most recently modified .json by mtime (reserved; rejected on write)
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEMORY_DIR = Path.home() / ".config" / "agentic-store" / "memory"
_FACTS_FILE = MEMORY_DIR / "facts.json"
_SESSION_FILE = MEMORY_DIR / "session.jsonl"
_STRATEGY_FILE = MEMORY_DIR / "strategy.md"
_CHECKPOINTS_DIR = MEMORY_DIR / "checkpoints"

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _now_human() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lock(fh) -> None:
    if sys.platform != "win32":
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass


def _unlock(fh) -> None:
    if sys.platform != "win32":
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass


def _read_facts_raw() -> dict:
    if not _FACTS_FILE.exists():
        return {}
    try:
        return json.loads(_FACTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_facts_raw(data: dict) -> None:
    _ensure_dir(MEMORY_DIR)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    # Atomic write with locking
    fd, tmp = tempfile.mkstemp(dir=MEMORY_DIR, prefix=".facts_tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            _lock(fh)
            fh.write(payload)
            _unlock(fh)
        os.replace(tmp, _FACTS_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ─── Facts ────────────────────────────────────────────────────────────────────

def write_fact(key: str, value: Any, category: str = "facts") -> None:
    """Write or update a fact."""
    facts = _read_facts_raw()
    now = _now_human()
    existing = facts.get(key, {})
    facts[key] = {
        "key": key,
        "value": value,
        "category": category,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    _write_facts_raw(facts)


def read_fact(key: str, category: str = "facts") -> dict | None:
    """Return a fact by key, or None."""
    facts = _read_facts_raw()
    entry = facts.get(key)
    if entry and (category == "facts" or entry.get("category") == category):
        return entry
    return None


def list_facts(category: str = "facts") -> list[dict]:
    """Return all facts, optionally filtered by category."""
    facts = _read_facts_raw()
    result = list(facts.values())
    if category != "facts":
        result = [f for f in result if f.get("category") == category]
    return sorted(result, key=lambda f: f.get("updated_at", ""))


def delete_fact(key: str) -> bool:
    """Delete a fact. Returns True if it existed."""
    facts = _read_facts_raw()
    if key in facts:
        del facts[key]
        _write_facts_raw(facts)
        return True
    return False


# ─── Session log ──────────────────────────────────────────────────────────────

def append_log(entry: dict) -> None:
    """Append one JSON line to session.jsonl. Auto-adds timestamp."""
    _ensure_dir(MEMORY_DIR)
    entry = {"timestamp": _now_human(), **entry}
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(_SESSION_FILE, "a", encoding="utf-8") as fh:
        fh.write(line)


def read_logs(limit: int = 50) -> list[dict]:
    """Return the last `limit` log entries (newest last)."""
    if not _SESSION_FILE.exists():
        return []
    lines = []
    try:
        with open(_SESSION_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        return []
    return lines[-limit:]


# ─── Strategy ─────────────────────────────────────────────────────────────────

def write_strategy(content: str) -> None:
    """Overwrite strategy.md with new content."""
    _ensure_dir(MEMORY_DIR)
    _STRATEGY_FILE.write_text(content, encoding="utf-8")


def read_strategy() -> str:
    """Return strategy.md content, or empty string."""
    if not _STRATEGY_FILE.exists():
        return ""
    try:
        return _STRATEGY_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""


# ─── Checkpoints ──────────────────────────────────────────────────────────────

def _checkpoint_path(name: str) -> Path:
    return _CHECKPOINTS_DIR / f"{name}.json"


def _validate_name(name: str) -> str | None:
    """Return error string if invalid, else None."""
    if name == "latest":
        return "'latest' is a reserved name"
    if not _NAME_RE.match(name):
        return "Name must contain only letters, digits, hyphens, and underscores"
    return None


def save_checkpoint(name: str | None, data: dict) -> str:
    """
    Save a checkpoint. Auto-generates a timestamped name if name is None.
    Returns the name used.
    Raises ValueError on invalid name.
    """
    if name is None:
        name = f"checkpoint_{_now_iso()}"
    err = _validate_name(name)
    if err:
        raise ValueError(err)

    _ensure_dir(_CHECKPOINTS_DIR)
    payload = {"name": name, **data}
    if "timestamp" not in payload:
        payload["timestamp"] = _now_human()

    _checkpoint_path(name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return name


def load_checkpoint(name: str) -> dict | None:
    """
    Load a checkpoint by name.
    'latest' resolves to the most recently modified checkpoint.
    Returns None if not found.
    """
    if name == "latest":
        cp_dir = _CHECKPOINTS_DIR
        if not cp_dir.exists():
            return None
        candidates = [p for p in cp_dir.glob("*.json") if p.is_file()]
        if not candidates:
            return None
        path = max(candidates, key=lambda p: p.stat().st_mtime)
    else:
        path = _checkpoint_path(name)

    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_checkpoints() -> list[dict]:
    """Return checkpoint summaries sorted by mtime desc."""
    cp_dir = _CHECKPOINTS_DIR
    if not cp_dir.exists():
        return []
    result = []
    for path in sorted(cp_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append({
                "name": path.stem,
                "timestamp": data.get("timestamp", ""),
                "task": data.get("task", ""),
                "client": data.get("client", ""),
            })
        except (json.JSONDecodeError, OSError):
            pass
    return result


def delete_checkpoint(name: str) -> bool:
    """Delete a checkpoint. Returns True if it existed."""
    path = _checkpoint_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


# ─── Search ───────────────────────────────────────────────────────────────────

def search_all(query: str) -> list[dict]:
    """
    Full-text search across facts, strategy, and checkpoint metadata.
    Returns list of {source, key/name, snippet, score}.
    """
    q = query.lower()
    results = []

    # Search facts
    for fact in _read_facts_raw().values():
        text = f"{fact.get('key', '')} {fact.get('value', '')} {fact.get('category', '')}".lower()
        if q in text:
            results.append({
                "source": "fact",
                "key": fact["key"],
                "category": fact.get("category", "facts"),
                "snippet": str(fact.get("value", ""))[:120],
            })

    # Search strategy
    strategy = read_strategy()
    if q in strategy.lower():
        # Find surrounding context
        idx = strategy.lower().find(q)
        start = max(0, idx - 60)
        snippet = ("…" if start else "") + strategy[start:idx + len(q) + 60] + "…"
        results.append({
            "source": "strategy",
            "key": "strategy.md",
            "snippet": snippet.strip(),
        })

    # Search checkpoints
    for cp in list_checkpoints():
        text = f"{cp['name']} {cp['task']} {cp['client']}".lower()
        if q in text:
            results.append({
                "source": "checkpoint",
                "key": cp["name"],
                "snippet": cp.get("task", "")[:120],
            })

    return results


# ─── Project files (plan, milestones, learnings, changelog) ──────────────────

def read_project_file(filename: str) -> str:
    """Read a named markdown file from MEMORY_DIR. Returns '' if missing."""
    path = MEMORY_DIR / filename
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_project_file(filename: str, content: str) -> None:
    """Atomically write content to MEMORY_DIR/<filename>."""
    _ensure_dir(MEMORY_DIR)
    path = MEMORY_DIR / filename
    fd, tmp = tempfile.mkstemp(dir=MEMORY_DIR, prefix=".proj_tmp_", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def append_project_file(filename: str, content: str) -> None:
    """Append content to MEMORY_DIR/<filename>."""
    _ensure_dir(MEMORY_DIR)
    path = MEMORY_DIR / filename
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(content)


# ─── Status (for webapp) ──────────────────────────────────────────────────────

def get_status() -> dict:
    """Return memory summary for the webapp status panel."""
    checkpoints = list_checkpoints()
    last_cp = checkpoints[0]["name"] if checkpoints else None

    facts = _read_facts_raw()

    log_size_kb = 0.0
    if _SESSION_FILE.exists():
        log_size_kb = round(_SESSION_FILE.stat().st_size / 1024, 1)

    return {
        "available": True,
        "last_checkpoint": last_cp,
        "fact_count": len(facts),
        "log_size_kb": log_size_kb,
        "checkpoint_count": len(checkpoints),
    }
