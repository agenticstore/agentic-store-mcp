"""Bounded local directory inventory."""
from pathlib import Path
from typing import Any

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
_MAX_FILES = 5_000


def run(params: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    if not root.is_dir():
        return {"result": None, "error": f"Directory not found: {root}"}
    extensions = {str(value).lower() for value in params.get("file_extensions", [])}
    files: list[dict[str, Any]] = []
    total_size = 0
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _SKIP for part in relative.parts) or not path.is_file():
            continue
        if extensions and path.suffix.lower() not in extensions:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        files.append({"path": str(path), "size_bytes": size, "extension": path.suffix.lower() or None})
        total_size += size
        if len(files) >= _MAX_FILES:
            break
    return {"result": {"path": str(root), "files": files, "file_count": len(files),
            "total_size_bytes": total_size, "truncated": len(files) >= _MAX_FILES,
            "read_only": True}, "error": None}
