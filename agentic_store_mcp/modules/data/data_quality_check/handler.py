"""Read-only quality checks for tabular local data."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

_MAX_ROWS = 10_000
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _load_records(path_value: str, table: str | None, limit: int) -> tuple[list[dict[str, Any]], bool]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"File does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as stream:
            rows = list(csv.DictReader(stream))
    elif suffix in {".json", ".jsonl"}:
        if suffix == ".jsonl":
            with path.open(encoding="utf-8", errors="replace") as stream:
                rows = [json.loads(line) for line in stream if line.strip()]
        else:
            rows = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("JSON input must be an array of objects")
    elif suffix in {".db", ".sqlite", ".sqlite3"}:
        if not table:
            raise ValueError("'table' is required for SQLite input")
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            allowed = {item[0] for item in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if table not in allowed:
                raise ValueError("Unknown SQLite table")
            cursor = connection.execute(f'SELECT * FROM "{table.replace(chr(34), chr(34) * 2)}" LIMIT ?', (limit + 1,))
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            connection.close()
    else:
        raise ValueError("Supported formats: CSV, JSON, JSONL, SQLite")
    return rows[:limit], len(rows) > limit


def _kind(value: Any) -> str:
    if value is None or value == "":
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    text = str(value)
    try:
        int(text)
        return "integer"
    except ValueError:
        try:
            float(text)
            return "number"
        except ValueError:
            return "string"


def run(args: dict[str, Any]) -> dict[str, Any]:
    path = args.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("'path' is required")
    limit = min(max(int(args.get("max_rows", _MAX_ROWS)), 1), _MAX_ROWS)
    max_null_fraction = float(args.get("max_null_fraction", 0.2))
    if not 0 <= max_null_fraction <= 1:
        raise ValueError("'max_null_fraction' must be between 0 and 1")
    records, truncated = _load_records(path, args.get("table"), limit)
    columns = sorted({key for row in records for key in row})
    checks: list[dict[str, Any]] = []

    primary_key = args.get("primary_key")
    if primary_key:
        values = [row.get(primary_key) for row in records if row.get(primary_key) not in (None, "")]
        duplicate_count = sum(count - 1 for count in Counter(map(str, values)).values() if count > 1)
        checks.append({"name": "duplicate_keys", "status": "fail" if duplicate_count else "pass", "column": primary_key, "duplicates": duplicate_count})

    null_violations = []
    for column in columns:
        nulls = sum(row.get(column) in (None, "") for row in records)
        fraction = nulls / len(records) if records else 0
        if fraction > max_null_fraction:
            null_violations.append({"column": column, "nulls": nulls, "fraction": round(fraction, 4)})
    checks.append({"name": "null_thresholds", "status": "fail" if null_violations else "pass", "threshold": max_null_fraction, "violations": null_violations})

    expected_types = args.get("expected_types") or {}
    if not isinstance(expected_types, dict):
        raise ValueError("'expected_types' must be an object")
    type_violations = []
    for column in columns:
        kinds = Counter(_kind(row.get(column)) for row in records if row.get(column) not in (None, ""))
        expected = expected_types.get(column)
        if expected:
            bad = sum(count for kind, count in kinds.items() if kind != expected)
            if bad:
                type_violations.append({"column": column, "expected": expected, "observed": dict(kinds), "invalid": bad})
        elif len(kinds) > 1:
            type_violations.append({"column": column, "observed": dict(kinds), "reason": "mixed_types"})
    checks.append({"name": "type_drift", "status": "fail" if type_violations else "pass", "violations": type_violations})

    email_columns = args.get("email_columns") or [column for column in columns if "email" in column.lower()]
    if not isinstance(email_columns, list):
        raise ValueError("'email_columns' must be an array")
    email_violations = []
    for column in email_columns:
        invalid = sum(bool(row.get(column)) and not _EMAIL.fullmatch(str(row[column]).strip()) for row in records)
        if invalid:
            email_violations.append({"column": column, "invalid": invalid})
    checks.append({"name": "invalid_emails", "status": "fail" if email_violations else "pass", "violations": email_violations})

    reference_path = args.get("reference_path")
    if reference_path:
        local_key, reference_key = args.get("local_key"), args.get("reference_key")
        if not local_key or not reference_key:
            raise ValueError("'local_key' and 'reference_key' are required with 'reference_path'")
        reference_rows, _ = _load_records(reference_path, args.get("reference_table"), limit)
        reference_values = {str(row.get(reference_key)) for row in reference_rows if row.get(reference_key) not in (None, "")}
        gaps = sum(str(row.get(local_key)) not in reference_values for row in records if row.get(local_key) not in (None, ""))
        checks.append({"name": "referential_gaps", "status": "fail" if gaps else "pass", "local_key": local_key, "reference_key": reference_key, "missing": gaps})

    failed = sum(check["status"] == "fail" for check in checks)
    return {"read_only": True, "rows_checked": len(records), "truncated": truncated, "columns": columns, "checks": checks, "summary": {"passed": len(checks) - failed, "failed": failed}}
