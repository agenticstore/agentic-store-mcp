"""Read-only SQLite schema inspection for agent planning."""
import os
import sqlite3
from pathlib import Path
from typing import Any


_MAX_TABLES = 100


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _tables(connection: sqlite3.Connection, requested_table: str | None) -> list[str]:
    query = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    params: tuple[str, ...] = ()
    if requested_table:
        query += " AND name = ?"
        params = (requested_table,)
    query += " ORDER BY name LIMIT ?"
    return [row[0] for row in connection.execute(query, (*params, _MAX_TABLES))]


def _inspect_table(connection: sqlite3.Connection, table: str, include_row_counts: bool) -> dict[str, Any]:
    quoted = _quote_identifier(table)
    columns = [
        {"name": row[1], "type": row[2] or None, "not_null": bool(row[3]), "default": row[4], "primary_key_position": row[5]}
        for row in connection.execute(f"PRAGMA table_info({quoted})")
    ]
    indexes = [
        {"name": row[1], "unique": bool(row[2]), "origin": row[3], "partial": bool(row[4])}
        for row in connection.execute(f"PRAGMA index_list({quoted})")
    ]
    foreign_keys = [
        {"from_column": row[3], "to_table": row[2], "to_column": row[4], "on_update": row[5], "on_delete": row[6]}
        for row in connection.execute(f"PRAGMA foreign_key_list({quoted})")
    ]
    result: dict[str, Any] = {"name": table, "columns": columns, "indexes": indexes, "foreign_keys": foreign_keys}
    if include_row_counts:
        result["row_count"] = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
    return result


def run(params: dict[str, Any]) -> dict[str, Any]:
    requested_path = str(params.get("path") or "").strip()
    if not requested_path:
        return {"result": None, "error": "'path' is required"}
    path = Path(requested_path).expanduser().resolve()
    if not path.exists():
        return {"result": None, "error": f"Database file not found: {path}"}
    if not path.is_file():
        return {"result": None, "error": f"Path is not a database file: {path}"}
    if not os.access(path, os.R_OK):
        return {"result": None, "error": f"Permission denied: {path}"}

    requested_table = str(params.get("table") or "").strip() or None
    include_row_counts = bool(params.get("include_row_counts", False))
    try:
        with _connect_read_only(path) as connection:
            table_names = _tables(connection, requested_table)
            if requested_table and not table_names:
                return {"result": None, "error": f"Table not found: {requested_table}"}
            table_details = [_inspect_table(connection, table, include_row_counts) for table in table_names]
            return {
                "result": {
                    "path": str(path),
                    "engine": "sqlite",
                    "read_only": True,
                    "file_size_bytes": path.stat().st_size,
                    "table_count": len(table_details),
                    "tables": table_details,
                    "row_counts_included": include_row_counts,
                    "truncated": len(table_names) >= _MAX_TABLES,
                },
                "error": None,
            }
    except sqlite3.DatabaseError as exc:
        return {"result": None, "error": f"Could not inspect SQLite database: {exc}"}
    except OSError as exc:
        return {"result": None, "error": str(exc)}
