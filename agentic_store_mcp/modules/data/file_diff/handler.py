"""Bounded, read-only unified diffs for local text files."""
import difflib
from pathlib import Path
from typing import Any

_MAX_BYTES = 1024 * 1024
_MAX_LINES = 2_000


def _read(path: Path) -> list[str]:
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError(f"File exceeds {_MAX_BYTES} byte comparison limit: {path}")
    raw = path.read_bytes()
    if b"\x00" in raw[:8192]:
        raise ValueError(f"Binary files cannot be compared as text: {path}")
    return raw.decode("utf-8", errors="replace").splitlines(keepends=True)


def run(params: dict[str, Any]) -> dict[str, Any]:
    left = Path(str(params.get("left_path") or "").strip()).expanduser().resolve()
    right = Path(str(params.get("right_path") or "").strip()).expanduser().resolve()
    if not left.is_file() or not right.is_file():
        return {"result": None, "error": "left_path and right_path must be readable files"}
    context = max(0, min(int(params.get("context_lines", 3)), 20))
    try:
        diff = list(difflib.unified_diff(_read(left), _read(right), fromfile=str(left), tofile=str(right), n=context))
        truncated = len(diff) > _MAX_LINES
        return {"result": {"left_path": str(left), "right_path": str(right),
                "identical": not diff, "diff": "".join(diff[:_MAX_LINES]),
                "diff_lines": len(diff), "truncated": truncated, "read_only": True}, "error": None}
    except (OSError, ValueError) as exc:
        return {"result": None, "error": str(exc)}
