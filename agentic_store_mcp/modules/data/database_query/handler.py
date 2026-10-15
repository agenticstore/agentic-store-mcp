"""Guarded, read-only SQLite query tool."""
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

_MAX_ROWS = 500
_MAX_SECONDS = 5
_ALLOWED = re.compile(r"^\s*(?:EXPLAIN\s+)?SELECT\b", re.IGNORECASE | re.DOTALL)
_BANNED = re.compile(r"\b(?:INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|REPLACE|VACUUM|PRAGMA|ATTACH|DETACH|BEGIN|COMMIT|ROLLBACK|WITH)\b", re.IGNORECASE)


def _validate(query: str) -> str | None:
    normalized = query.strip()
    if not normalized:
        return "'query' is required"
    if ";" in normalized:
        return "Only one statement is allowed; omit semicolons."
    if not _ALLOWED.match(normalized) or _BANNED.search(normalized):
        return "Only a single SELECT or EXPLAIN SELECT statement is allowed."
    return None


def run(params: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    query = str(params.get("query") or "")
    error = _validate(query)
    if error:
        return {"result": None, "error": error}
    if not path.is_file():
        return {"result": None, "error": f"Database file not found: {path}"}
    max_rows = max(1, min(int(params.get("max_rows", 100)), _MAX_ROWS))
    started = time.monotonic()
    connection = None
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        connection.set_progress_handler(lambda: int(time.monotonic() - started > _MAX_SECONDS), 10000)
        cursor = connection.execute(query, tuple(params.get("parameters") or []))
        columns = [item[0] for item in cursor.description or []]
        rows = [dict(zip(columns, row)) for row in cursor.fetchmany(max_rows + 1)]
        return {"result": {"path": str(path), "columns": columns, "rows": rows[:max_rows], "row_count": min(len(rows), max_rows), "truncated": len(rows) > max_rows, "read_only": True}, "error": None}
    except sqlite3.DatabaseError as exc:
        return {"result": None, "error": f"Query failed: {exc}"}
    finally:
        if connection is not None:
            connection.close()
