"""Explicit, limited transformations of CSV and JSONL files."""
import csv
import json
from pathlib import Path
from typing import Any


def _read_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    raise ValueError("Supported input formats: .csv, .jsonl")


def _write_rows(path: Path, rows: list[dict[str, Any]], fmt: str) -> None:
    if fmt == "jsonl":
        with path.open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(params: dict[str, Any]) -> dict[str, Any]:
    if not params.get("confirmed"):
        return {"result": None, "error": "Set confirmed=true after reviewing input_path, output_path, and operation."}
    source = Path(str(params.get("input_path") or "").strip()).expanduser().resolve()
    output = Path(str(params.get("output_path") or "").strip()).expanduser().resolve()
    operation = str(params.get("operation") or "")
    if not source.is_file():
        return {"result": None, "error": f"Input file not found: {source}"}
    if source == output:
        return {"result": None, "error": "output_path must differ from input_path"}
    if output.exists():
        return {"result": None, "error": f"Output already exists: {output}"}
    if operation not in {"csv_to_jsonl", "jsonl_to_csv", "filter_equals", "select_columns"}:
        return {"result": None, "error": "Unknown operation"}
    try:
        rows = _read_rows(source)
        target_format = "jsonl" if operation == "csv_to_jsonl" else "csv"
        if operation == "jsonl_to_csv":
            target_format = "csv"
        if operation == "select_columns":
            columns = [str(column) for column in params.get("columns") or []]
            if not columns:
                return {"result": None, "error": "'columns' is required for select_columns"}
            rows = [{column: row.get(column) for column in columns} for row in rows]
            target_format = "jsonl" if output.suffix.lower() == ".jsonl" else "csv"
        if operation == "filter_equals":
            column = str(params.get("filter_column") or "")
            if not column or "filter_value" not in params:
                return {"result": None, "error": "filter_column and filter_value are required for filter_equals"}
            rows = [row for row in rows if str(row.get(column, "")) == str(params["filter_value"])]
            target_format = "jsonl" if output.suffix.lower() == ".jsonl" else "csv"
        expected_suffix = ".jsonl" if target_format == "jsonl" else ".csv"
        if output.suffix.lower() != expected_suffix:
            return {"result": None, "error": f"output_path must end in {expected_suffix} for {operation}"}
        _write_rows(output, rows, target_format)
        return {"result": {"input_path": str(source), "output_path": str(output), "operation": operation, "rows_written": len(rows), "written": True}, "error": None}
    except (OSError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        return {"result": None, "error": str(exc)}
