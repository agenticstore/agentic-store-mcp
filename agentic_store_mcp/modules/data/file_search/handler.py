"""Bounded literal text search across local text files."""
from pathlib import Path
from typing import Any

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
_MAX_FILES = 2000
_MAX_SIZE = 2 * 1024 * 1024


def run(params: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    query = str(params.get("query") or "")
    if not root.is_dir():
        return {"result": None, "error": f"Directory not found: {root}"}
    if not query:
        return {"result": None, "error": "'query' is required"}
    max_results = max(1, min(int(params.get("max_results", 50)), 200))
    case_sensitive = bool(params.get("case_sensitive", False))
    needle = query if case_sensitive else query.lower()
    extensions = {str(value).lower() for value in params.get("file_extensions", [])}
    matches: list[dict[str, Any]] = []
    scanned = 0
    for path in root.rglob("*"):
        relative_parts = path.parts[len(root.parts):]
        if any(part in _SKIP for part in relative_parts):
            continue
        if not path.is_file() or path.stat().st_size > _MAX_SIZE:
            continue
        if extensions and path.suffix.lower() not in extensions:
            continue
        scanned += 1
        if scanned > _MAX_FILES:
            break
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            haystack = line if case_sensitive else line.lower()
            if needle in haystack:
                matches.append({"path": str(path), "line": line_number, "excerpt": line[:500]})
                if len(matches) >= max_results:
                    return {"result": {"matches": matches, "match_count": len(matches), "files_scanned": scanned, "truncated": True, "read_only": True}, "error": None}
    return {"result": {"matches": matches, "match_count": len(matches), "files_scanned": scanned, "truncated": scanned > _MAX_FILES, "read_only": True}, "error": None}
