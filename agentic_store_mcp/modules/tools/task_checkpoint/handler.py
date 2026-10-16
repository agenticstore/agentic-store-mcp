"""Persist or retrieve a structured task checkpoint at an explicit local path."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def run(args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "read")
    path = Path(args.get("path", "")).expanduser().resolve()
    if not str(args.get("path", "")): raise ValueError("'path' is required")
    if action == "read":
        if not path.is_file(): raise ValueError("Checkpoint does not exist")
        return {"read_only": True, "checkpoint": json.loads(path.read_text())}
    if action == "write":
        if args.get("confirm_write") is not True: raise ValueError("Set confirm_write=true to save a checkpoint")
        checkpoint = args.get("checkpoint")
        if not isinstance(checkpoint, dict): raise ValueError("'checkpoint' must be an object")
        checkpoint.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(checkpoint, indent=2) + "\n")
        return {"written": True, "path": str(path), "checkpoint": checkpoint}
    raise ValueError("action must be read or write")
