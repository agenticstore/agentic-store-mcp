"""Bounded, read-only text-file reader."""
from pathlib import Path
from typing import Any

_MAX_LINES = 2_000


def run(params: dict[str, Any]) -> dict[str, Any]:
    requested = str(params.get("path") or "").strip()
    if not requested:
        return {"result": None, "error": "'path' is required"}
    path = Path(requested).expanduser().resolve()
    if not path.is_file():
        return {"result": None, "error": f"Readable file not found: {path}"}
    start_line = max(1, int(params.get("start_line", 1)))
    max_lines = max(1, min(int(params.get("max_lines", 200)), _MAX_LINES))
    try:
        with path.open("rb") as handle:
            if b"\x00" in handle.read(8192):
                return {"result": None, "error": "Binary files cannot be read as text"}
        with path.open(encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        selected = lines[start_line - 1 : start_line - 1 + max_lines]
        return {"result": {"path": str(path), "start_line": start_line,
                "end_line": start_line + len(selected) - 1, "content": "".join(selected),
                "truncated": len(lines) > start_line - 1 + len(selected), "read_only": True}, "error": None}
    except OSError as exc:
        return {"result": None, "error": str(exc)}
