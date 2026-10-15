"""Bounded, read-only local file inspection."""
import hashlib
from pathlib import Path
from typing import Any

_MAX_PREVIEW = 8192
_CHUNK = 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def run(params: dict[str, Any]) -> dict[str, Any]:
    requested = str(params.get("path") or "").strip()
    if not requested:
        return {"result": None, "error": "'path' is required"}
    path = Path(requested).expanduser().resolve()
    if not path.is_file():
        return {"result": None, "error": f"Readable file not found: {path}"}
    preview_bytes = max(1, min(int(params.get("preview_bytes", 2048)), _MAX_PREVIEW))
    try:
        with path.open("rb") as handle:
            raw = handle.read(preview_bytes)
        binary = b"\x00" in raw
        preview = None if binary else raw.decode("utf-8", errors="replace")
        result: dict[str, Any] = {
            "path": str(path), "name": path.name, "extension": path.suffix.lower() or None,
            "size_bytes": path.stat().st_size, "kind": "binary" if binary else "text",
            "encoding": None if binary else "utf-8", "preview": preview,
            "preview_truncated": path.stat().st_size > len(raw), "read_only": True,
        }
        if not binary:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                result["line_count"] = sum(1 for _ in handle)
        if params.get("include_hash", True):
            result["sha256"] = _sha256(path)
        return {"result": result, "error": None}
    except OSError as exc:
        return {"result": None, "error": str(exc)}
