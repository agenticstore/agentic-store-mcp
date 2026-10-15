"""Deterministic random sample of local files."""
import random
from pathlib import Path
from typing import Any

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
_MAX_FILES = 5_000


def run(params: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    if not root.is_dir():
        return {"result": None, "error": f"Directory not found: {root}"}
    count = max(1, min(int(params.get("count", 5)), 100))
    extensions = {str(value).lower() for value in params.get("file_extensions", [])}
    candidates = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _SKIP for part in relative.parts) or not path.is_file():
            continue
        if not extensions or path.suffix.lower() in extensions:
            candidates.append(str(path))
        if len(candidates) >= _MAX_FILES:
            break
    seed = params.get("seed")
    random.Random(str(seed) if seed is not None else None).shuffle(candidates)
    return {"result": {"path": str(root), "files": candidates[:count],
            "candidate_count": len(candidates), "truncated": len(candidates) >= _MAX_FILES,
            "read_only": True}, "error": None}
