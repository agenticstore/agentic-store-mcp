"""Bounded, read-only query operations over local structured files."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

_MAX_ROWS = 10_000
_MAX_OUTPUT = 500


def _records(value: str, limit: int) -> tuple[list[dict[str, Any]], bool]:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"File does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as stream:
            data = list(csv.DictReader(stream))
    elif suffix == ".jsonl":
        with path.open(encoding="utf-8", errors="replace") as stream:
            data = [json.loads(line) for line in stream if line.strip()]
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    else:
        raise ValueError("Supported formats: CSV, JSON, JSONL")
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError("Input must contain an array of objects")
    return data[:limit], len(data) > limit


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq": return actual == expected or str(actual) == str(expected)
    if operator == "ne": return not _matches(actual, "eq", expected)
    if operator == "contains": return str(expected).lower() in str(actual or "").lower()
    if operator == "in": return any(_matches(actual, "eq", item) for item in expected) if isinstance(expected, list) else False
    actual_num, expected_num = _number(actual), _number(expected)
    if actual_num is None or expected_num is None: return False
    return {"gt": actual_num > expected_num, "gte": actual_num >= expected_num, "lt": actual_num < expected_num, "lte": actual_num <= expected_num}.get(operator, False)


def _aggregate(rows: list[dict[str, Any]], operations: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in operations:
        column, operation = item.get("column"), item.get("operation")
        if operation == "count":
            result[f"count_{column or 'rows'}"] = len(rows) if not column else sum(row.get(column) not in (None, "") for row in rows)
            continue
        values = [number for row in rows if (number := _number(row.get(column))) is not None]
        key = f"{operation}_{column}"
        if operation == "sum": result[key] = sum(values)
        elif operation == "avg": result[key] = sum(values) / len(values) if values else None
        elif operation == "min": result[key] = min(values) if values else None
        elif operation == "max": result[key] = max(values) if values else None
        else: raise ValueError("Aggregation operation must be count, sum, avg, min, or max")
    return result


def run(args: dict[str, Any]) -> dict[str, Any]:
    path = args.get("path")
    if not isinstance(path, str) or not path: raise ValueError("'path' is required")
    rows, truncated = _records(path, _MAX_ROWS)
    filters = args.get("filters", [])
    if not isinstance(filters, list): raise ValueError("'filters' must be an array")
    for item in filters:
        if not isinstance(item, dict) or not {"column", "operator", "value"} <= item.keys():
            raise ValueError("Each filter requires column, operator, and value")
        if item["operator"] not in {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "in"}:
            raise ValueError("Unsupported filter operator")
    rows = [row for row in rows if all(_matches(row.get(item["column"]), item["operator"], item["value"]) for item in filters)]
    group_by, aggregations = args.get("group_by"), args.get("aggregations", [])
    if aggregations and not isinstance(aggregations, list): raise ValueError("'aggregations' must be an array")
    if aggregations:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows: groups[str(row.get(group_by)) if group_by else "all"].append(row)
        result_rows = [{**({group_by: key} if group_by else {}), **_aggregate(group, aggregations)} for key, group in groups.items()]
    else:
        result_rows = rows
    sort = args.get("sort")
    if sort:
        if not isinstance(sort, dict) or sort.get("direction", "asc") not in {"asc", "desc"}: raise ValueError("sort requires column and direction asc or desc")
        column = sort.get("column")
        result_rows.sort(key=lambda row: (row.get(column) is None, str(row.get(column, "")).lower()), reverse=sort.get("direction") == "desc")
    select = args.get("select")
    if select and not aggregations:
        if not isinstance(select, list): raise ValueError("'select' must be an array")
        result_rows = [{column: row.get(column) for column in select} for row in result_rows]
    limit = min(max(int(args.get("limit", 100)), 1), _MAX_OUTPUT)
    output_truncated = len(result_rows) > limit
    return {"read_only": True, "rows_matched": len(rows), "rows_returned": min(len(result_rows), limit), "source_truncated": truncated, "output_truncated": output_truncated, "rows": result_rows[:limit]}
