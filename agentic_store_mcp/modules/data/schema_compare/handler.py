"""Read-only schema comparisons for flat files and SQLite tables."""
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any


def _schema(path: Path, table: str | None) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return {column: "string" for column in (csv.DictReader(handle).fieldnames or [])}
    if suffix in {".json", ".jsonl"}:
        if suffix == ".jsonl":
            with path.open(encoding="utf-8") as handle:
                row = next((json.loads(line) for line in handle if line.strip()), {})
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            row = data[0] if isinstance(data, list) and data else {}
        if not isinstance(row, dict):
            raise ValueError("JSON source must contain object rows")
        return {key: type(value).__name__ for key, value in row.items()}
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        selected = table or (tables[0] if len(tables) == 1 else None)
        if not selected:
            raise ValueError("Specify table for a SQLite database with multiple tables")
        return {row[1]: row[2] or "unknown" for row in connection.execute(f'PRAGMA table_info("{selected.replace(chr(34), chr(34) * 2)}")')}
    finally:
        connection.close()


def run(params: dict[str, Any]) -> dict[str, Any]:
    left = Path(str(params.get("left_path") or "").strip()).expanduser().resolve()
    right = Path(str(params.get("right_path") or "").strip()).expanduser().resolve()
    if not left.is_file() or not right.is_file():
        return {"result": None, "error": "Both left_path and right_path must be readable files."}
    try:
        left_schema = _schema(left, params.get("left_table"))
        right_schema = _schema(right, params.get("right_table"))
        shared = sorted(set(left_schema) & set(right_schema))
        return {"result": {"left_path": str(left), "right_path": str(right), "left_only": sorted(set(left_schema) - set(right_schema)), "right_only": sorted(set(right_schema) - set(left_schema)), "shared": shared, "type_differences": [{"column": name, "left_type": left_schema[name], "right_type": right_schema[name]} for name in shared if left_schema[name] != right_schema[name]], "compatible": set(left_schema) == set(right_schema), "read_only": True}, "error": None}
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.DatabaseError, csv.Error) as exc:
        return {"result": None, "error": str(exc)}
