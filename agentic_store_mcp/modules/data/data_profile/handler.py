"""Small, local, dependency-free data profiler for CSV and JSON records."""
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _records(path: Path, limit: int) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
            return [dict(row) for _, row in zip(range(limit), csv.DictReader(handle))]
    if suffix == ".jsonl":
        with path.open(encoding="utf-8", errors="replace") as handle:
            return [json.loads(line) for _, line in zip(range(limit), handle) if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, list):
        raise ValueError("JSON must contain a top-level array of objects")
    if not all(isinstance(row, dict) for row in data[:limit]):
        raise ValueError("Dataset rows must be JSON objects")
    return data[:limit]


def _kind(value: Any) -> str:
    if value is None or value == "":
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def run(params: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    if not path.is_file():
        return {"result": None, "error": f"Data file not found: {path}"}
    if path.suffix.lower() not in {".csv", ".json", ".jsonl"}:
        return {"result": None, "error": "Supported formats: .csv, .json, .jsonl"}
    max_rows = max(1, min(int(params.get("max_rows", 1000)), 10000))
    sample_rows = max(1, min(int(params.get("sample_rows", 5)), 20))
    try:
        rows = _records(path, max_rows)
        columns = sorted({key for row in rows for key in row})
        profiles, pii = [], Counter()
        for column in columns:
            values = [row.get(column) for row in rows]
            kinds = Counter(_kind(value) for value in values)
            pii["email"] += sum(isinstance(value, str) and bool(_EMAIL.match(value)) for value in values)
            profiles.append({"name": column, "types": dict(kinds), "null_count": kinds.get("null", 0), "unique_count": len({str(value) for value in values if value not in (None, "")})})
        duplicates = len(rows) - len({json.dumps(row, sort_keys=True, default=str) for row in rows})
        return {"result": {"path": str(path), "format": path.suffix.lower()[1:], "rows_profiled": len(rows), "columns": profiles, "duplicate_rows": duplicates, "pii_categories": {key: value for key, value in pii.items() if value}, "sample_rows": rows[:sample_rows], "truncated": len(rows) >= max_rows, "read_only": True}, "error": None}
    except (OSError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        return {"result": None, "error": str(exc)}
