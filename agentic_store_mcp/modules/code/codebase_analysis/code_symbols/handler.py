"""Read-only code symbol inventory for local Python and JavaScript-family files."""
import ast
import re
from pathlib import Path
from typing import Any

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
_MAX_FILES = 2_000
_MAX_SIZE = 512 * 1024
_JS_SYMBOL = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const|let)\s+([A-Za-z_$][\w$]*)", re.MULTILINE)


def _python_symbols(path: Path, text: str) -> list[dict[str, Any]]:
    tree = ast.parse(text, filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append({"name": node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                          "line": node.lineno})
    return found


def _js_symbols(text: str) -> list[dict[str, Any]]:
    return [{"name": match.group(1), "kind": "symbol", "line": text[:match.start()].count("\n") + 1}
            for match in _JS_SYMBOL.finditer(text)]


def run(params: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    if not root.is_dir():
        return {"result": None, "error": f"Directory not found: {root}"}
    requested = str(params.get("query") or "").lower()
    extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}
    supplied = {str(value).lower() for value in params.get("file_extensions", [])}
    if supplied:
        extensions &= supplied
    matches, scanned = [], 0
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _SKIP for part in relative.parts) or not path.is_file() or path.suffix.lower() not in extensions:
            continue
        try:
            if path.stat().st_size > _MAX_SIZE:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            symbols = _python_symbols(path, text) if path.suffix.lower() == ".py" else _js_symbols(text)
        except (OSError, SyntaxError):
            continue
        scanned += 1
        for symbol in symbols:
            if not requested or requested in symbol["name"].lower():
                matches.append({"path": str(path), **symbol})
        if scanned >= _MAX_FILES:
            break
    max_results = max(1, min(int(params.get("max_results", 100)), 500))
    return {"result": {"symbols": matches[:max_results], "symbol_count": len(matches[:max_results]),
            "files_scanned": scanned, "truncated": len(matches) > max_results or scanned >= _MAX_FILES,
            "read_only": True}, "error": None}
