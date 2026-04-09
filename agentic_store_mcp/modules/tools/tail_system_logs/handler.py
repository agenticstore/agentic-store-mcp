"""
tail_system_logs — read the last N lines of a local log file.

Fast: uses seek-from-end to avoid reading the whole file.
"""
from __future__ import annotations

import os


_MAX_LINES = 1000
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB read cap — avoids loading enormous logs


def _tail_file(path: str, n: int, encoding: str) -> list[str]:
    """Efficiently read the last n lines by seeking from the end of the file."""
    size = os.path.getsize(path)
    read_size = min(size, _MAX_BYTES)

    with open(path, "rb") as f:
        if read_size < size:
            f.seek(-read_size, 2)  # seek from end
            raw = f.read()
            # Drop partial first line (we may have seeked mid-line)
            raw = raw[raw.find(b"\n") + 1:]
        else:
            raw = f.read()

    text = raw.decode(encoding, errors="replace")
    lines = text.splitlines()
    return lines[-n:] if len(lines) > n else lines


def run(params: dict) -> dict:
    path = (params.get("path") or "").strip()
    if not path:
        return {"result": None, "error": "'path' is required"}

    n = int(params.get("lines", 50))
    n = max(1, min(n, _MAX_LINES))

    filter_str = (params.get("filter") or "").strip().lower()
    encoding = (params.get("encoding") or "utf-8").strip()

    try:
        if not os.path.exists(path):
            return {"result": None, "error": f"File not found: {path}"}
        if not os.path.isfile(path):
            return {"result": None, "error": f"Path is not a file: {path}"}
        if not os.access(path, os.R_OK):
            return {"result": None, "error": f"Permission denied: {path}"}

        lines = _tail_file(path, n, encoding)

        if filter_str:
            lines = [ln for ln in lines if filter_str in ln.lower()]

        file_size_kb = round(os.path.getsize(path) / 1024, 1)

        return {
            "result": {
                "path": path,
                "lines": lines,
                "line_count": len(lines),
                "requested_lines": n,
                "filter": filter_str or None,
                "file_size_kb": file_size_kb,
                "truncated": file_size_kb * 1024 > _MAX_BYTES,
            },
            "error": None,
        }

    except UnicodeDecodeError:
        return {
            "result": None,
            "error": f"Could not decode file with encoding '{encoding}'. Try encoding='latin-1'.",
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
