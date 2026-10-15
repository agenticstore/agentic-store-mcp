"""Find textual imports, definitions, and usages for Python and TypeScript symbols."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
_DEFAULT_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}
_MAX_FILES = 2_000
_MAX_SIZE = 512 * 1024


def _kind(line: str, suffix: str, symbol: str) -> str:
    stripped = line.strip()
    if suffix == ".py":
        if re.match(rf"(?:from\s+[^\s]+\s+import\s+.*\b{re.escape(symbol)}\b|import\s+.*\b{re.escape(symbol)}\b)", stripped): return "import"
        if re.match(rf"(?:async\s+def|def|class)\s+{re.escape(symbol)}\b", stripped): return "definition"
    else:
        if re.match(rf"import\s+.*\b{re.escape(symbol)}\b|.*require\(.*{re.escape(symbol)}", stripped): return "import"
        if re.match(rf"(?:export\s+)?(?:function|class|const|let|var|interface|type)\s+{re.escape(symbol)}\b", stripped): return "definition"
    return "reference"


def run(args: dict[str, Any]) -> dict[str, Any]:
    root_value, symbol = args.get("path"), args.get("symbol")
    if not isinstance(root_value, str) or not root_value: raise ValueError("'path' is required")
    if not isinstance(symbol, str) or not symbol.strip(): raise ValueError("'symbol' is required")
    root = Path(root_value).expanduser().resolve()
    if not root.is_dir(): raise ValueError("'path' must be a directory")
    extensions = args.get("extensions") or sorted(_DEFAULT_EXTENSIONS)
    allowed = {item if item.startswith(".") else f".{item}" for item in extensions}
    max_results = min(max(int(args.get("max_results", 200)), 1), 1_000)
    pattern = re.compile(rf"(?<![\w$]){re.escape(symbol)}(?![\w$])")
    matches: list[dict[str, Any]] = []
    scanned = 0
    for file_path in root.rglob("*"):
        if scanned >= _MAX_FILES or len(matches) >= max_results: break
        if any(part in _SKIP for part in file_path.parts) or not file_path.is_file() or file_path.suffix not in allowed: continue
        if file_path.stat().st_size > _MAX_SIZE: continue
        scanned += 1
        try: lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError: continue
        for line_number, line in enumerate(lines, 1):
            if pattern.search(line):
                matches.append({"path": str(file_path.relative_to(root)), "line": line_number, "kind": _kind(line, file_path.suffix, symbol), "excerpt": line.strip()[:300]})
                if len(matches) >= max_results: break
    counts = {kind: sum(item["kind"] == kind for item in matches) for kind in ("import", "definition", "reference")}
    return {"read_only": True, "symbol": symbol, "files_scanned": scanned, "result_truncated": len(matches) >= max_results, "counts": counts, "matches": matches}
