"""
python_lint_checker — static analysis for Python files.

Inspired by the check categories of ruff and pyflakes.
Pure Python, zero external dependencies. Uses the built-in `ast` module.

Check categories:
  imports    — unused, star, duplicate, multi-line imports
  bugs       — mutable defaults, bare except, assert-tuple, None/bool comparisons,
               builtin shadowing, silenced exceptions, duplicate dict keys
  style      — line length, trailing whitespace, tabs/spaces, semicolons,
               print() calls, TODO comments
  complexity — too many args, long functions, deep nesting,
               many returns, high branch count

Error codes:
  IMP001  Unused import
  IMP002  Star import
  IMP003  Duplicate import
  IMP004  Multiple imports on one line
  BUG001  Mutable default argument
  BUG002  Bare except clause
  BUG003  Assert with tuple (always True)
  BUG004  Comparison to None with == instead of is
  BUG005  Comparison to True/False with == instead of is
  BUG006  Name shadows a Python builtin
  BUG007  Exception caught and silenced with pass
  BUG008  Duplicate key in dict literal
  STY001  Line too long
  STY002  Trailing whitespace
  STY003  Mixed tabs and spaces
  STY004  Multiple statements on one line (semicolon)
  STY005  print() call found
  STY006  TODO / FIXME / HACK comment
  CPX001  Too many function arguments
  CPX002  Function too long
  CPX003  Deeply nested code
  CPX004  Too many return statements in a function
  CPX005  Too many branches in a function (cyclomatic complexity)
"""
import ast
import re
from pathlib import Path
from typing import Any

# ─── Thresholds (opinionated defaults, match common community standards) ──────

DEFAULT_MAX_LINE_LENGTH = 88       # matches black / ruff default
DEFAULT_MAX_ARGS = 7
DEFAULT_MAX_FUNCTION_LINES = 60
DEFAULT_MAX_NESTING = 4
DEFAULT_MAX_RETURNS = 5
DEFAULT_MAX_BRANCHES = 10

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "dist", "build", ".tox",
}

PYTHON_BUILTINS = {
    "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray",
    "bytes", "callable", "chr", "classmethod", "compile", "complex",
    "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec",
    "filter", "float", "format", "frozenset", "getattr", "globals",
    "hasattr", "hash", "help", "hex", "id", "input", "int", "isinstance",
    "issubclass", "iter", "len", "list", "locals", "map", "max",
    "memoryview", "min", "next", "object", "oct", "open", "ord", "pow",
    "print", "property", "range", "repr", "reversed", "round", "set",
    "setattr", "slice", "sorted", "staticmethod", "str", "sum", "super",
    "tuple", "type", "vars", "zip",
}

MUTABLE_DEFAULT_TYPES = (ast.List, ast.Dict, ast.Set)

ALL_CATEGORIES = {"imports", "bugs", "style", "complexity"}


# ─── Issue factory ────────────────────────────────────────────────────────────


def _issue(line: int, col: int, code: str, message: str, severity: str, category: str) -> dict:
    """Build a standardised issue dict returned in findings lists."""
    return {
        "line": line,
        "col": col,
        "code": code,
        "message": message,
        "severity": severity,
        "category": category,
    }


# ─── Line-based checks (style) ────────────────────────────────────────────────


def _check_style_lines(source: str, max_line_length: int) -> list[dict]:
    """Run line-based style checks (line length, trailing whitespace, tabs, semicolons, TODOs)."""
    issues: list[dict] = []
    lines = source.split("\n")
    has_tabs = False
    has_spaces = False

    for i, line in enumerate(lines, 1):
        # Trailing whitespace (check before stripping)
        if line != line.rstrip():
            issues.append(_issue(i, len(line.rstrip()) + 1, "STY002", "Trailing whitespace", "WARNING", "style"))

        # Line too long
        if len(line) > max_line_length:
            issues.append(_issue(
                i, max_line_length + 1, "STY001",
                f"Line too long ({len(line)} > {max_line_length} characters)",
                "WARNING", "style",
            ))

        # Mixed indentation tracking
        if line.startswith("\t"):
            has_tabs = True
        elif line.startswith("    "):
            has_spaces = True

        # Multiple statements on one line via semicolon (skip comments and strings)
        stripped = line.strip()
        if not stripped.startswith("#"):
            # Find semicolons not inside strings (rough heuristic — handles common cases)
            in_str = False
            str_char = ""
            for j, ch in enumerate(stripped):
                if ch in ('"', "'") and not in_str:
                    in_str = True
                    str_char = ch
                elif in_str and ch == str_char:
                    in_str = False
                elif ch == ";" and not in_str:
                    issues.append(_issue(
                        i, j + 1, "STY004",
                        "Multiple statements on one line (semicolon) — use separate lines",
                        "WARNING", "style",
                    ))
                    break

        # TODO / FIXME / HACK / XXX comments
        m = re.search(r"#\s*(TODO|FIXME|HACK|XXX|BUG)\b", line, re.IGNORECASE)
        if m:
            tag = m.group(1).upper()
            issues.append(_issue(i, m.start() + 1, "STY006", f"{tag} comment", "INFO", "style"))

    if has_tabs and has_spaces:
        issues.append(_issue(1, 1, "STY003",
            "Mixed tabs and spaces for indentation — use spaces consistently (PEP 8)",
            "ERROR", "style"))

    return issues


# ─── AST visitor ─────────────────────────────────────────────────────────────


class _Analyzer(ast.NodeVisitor):
    """
    Single-pass AST walker. Collects imported names, used names, and issues
    for all AST-based check categories.
    """

    def __init__(self, active: set[str]):
        self.active = active

        # Import tracking: list of {name, local_name, line, kind}
        self._imports: list[dict] = []
        # All names referenced via Load context
        self._used: set[str] = set()
        # All string constants (for __all__ usage detection)
        self._string_constants: set[str] = set()

        self._nesting: int = 0
        self.issues: list[dict] = []

    # ── Import nodes ──────────────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import) -> None:
        if "imports" in self.active:
            if len(node.names) > 1:
                names_str = ", ".join(a.name for a in node.names)
                self.issues.append(_issue(
                    node.lineno, 1, "IMP004",
                    f"Multiple imports on one line: 'import {names_str}' — use one import per line",
                    "WARNING", "imports",
                ))

        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self._imports.append({"name": alias.name, "local": local, "line": node.lineno})

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                if "imports" in self.active:
                    self.issues.append(_issue(
                        node.lineno, 1, "IMP002",
                        f"Star import from '{module}' — import specific names instead",
                        "WARNING", "imports",
                    ))
                continue
            local = alias.asname or alias.name
            full = f"{module}.{alias.name}" if module else alias.name
            self._imports.append({"name": full, "local": local, "line": node.lineno})

        self.generic_visit(node)

    # ── Name usage ────────────────────────────────────────────────────────────

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._used.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Track root of attribute chains: e.g. `os.path.join` → track `os`
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            self._used.add(root.id)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._string_constants.add(node.value)
        self.generic_visit(node)

    # ── Builtin shadowing ─────────────────────────────────────────────────────

    def visit_Assign(self, node: ast.Assign) -> None:
        if "bugs" in self.active:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in PYTHON_BUILTINS:
                    self.issues.append(_issue(
                        node.lineno, target.col_offset + 1, "BUG006",
                        f"'{target.id}' shadows a Python builtin",
                        "WARNING", "bugs",
                    ))
        self.generic_visit(node)

    # ── Exception handlers ────────────────────────────────────────────────────

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if "bugs" in self.active:
            if node.type is None:
                self.issues.append(_issue(
                    node.lineno, 1, "BUG002",
                    "Bare 'except:' catches everything including SystemExit and KeyboardInterrupt — catch specific exceptions",
                    "WARNING", "bugs",
                ))
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                self.issues.append(_issue(
                    node.lineno, 1, "BUG007",
                    "Exception caught and silenced with 'pass' — error information is lost",
                    "WARNING", "bugs",
                ))
        self.generic_visit(node)

    # ── Assert ────────────────────────────────────────────────────────────────

    def visit_Assert(self, node: ast.Assert) -> None:
        if "bugs" in self.active and isinstance(node.test, ast.Tuple):
            self.issues.append(_issue(
                node.lineno, 1, "BUG003",
                "assert (condition, message) tests a tuple — it always passes. Use: assert condition, message",
                "ERROR", "bugs",
            ))
        self.generic_visit(node)

    # ── Comparisons ───────────────────────────────────────────────────────────

    def visit_Compare(self, node: ast.Compare) -> None:
        if "bugs" in self.active:
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant):
                    op_str = "==" if isinstance(op, ast.Eq) else "!="
                    if comp.value is None:
                        self.issues.append(_issue(
                            node.lineno, node.col_offset + 1, "BUG004",
                            f"Use 'is None' / 'is not None' instead of '{op_str} None'",
                            "WARNING", "bugs",
                        ))
                    elif isinstance(comp.value, bool):
                        self.issues.append(_issue(
                            node.lineno, node.col_offset + 1, "BUG005",
                            f"Use 'is {comp.value}' or a boolean expression instead of '{op_str} {comp.value}'",
                            "WARNING", "bugs",
                        ))
        self.generic_visit(node)

    # ── Dict literal ──────────────────────────────────────────────────────────

    def visit_Dict(self, node: ast.Dict) -> None:
        if "bugs" in self.active:
            seen: list = []
            for key in node.keys:
                if key is None:  # **unpacking
                    continue
                if isinstance(key, ast.Constant):
                    if key.value in seen:
                        self.issues.append(_issue(
                            key.lineno, key.col_offset + 1, "BUG008",
                            f"Duplicate key '{key.value!r}' in dict literal — earlier value is silently overwritten",
                            "ERROR", "bugs",
                        ))
                    seen.append(key.value)
        self.generic_visit(node)

    # ── print() ───────────────────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call) -> None:
        if "style" in self.active:
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                self.issues.append(_issue(
                    node.lineno, node.col_offset + 1, "STY005",
                    "print() call — use logging for production code",
                    "INFO", "style",
                ))
        self.generic_visit(node)

    # ── Functions ─────────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self._nesting += 1
        self.generic_visit(node)
        self._nesting -= 1

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def _check_function(self, node: ast.FunctionDef) -> None:
        args = node.args
        all_args = (
            args.posonlyargs
            + args.args
            + args.kwonlyargs
            + ([args.vararg] if args.vararg else [])
            + ([args.kwarg] if args.kwarg else [])
        )

        if "complexity" in self.active:
            # Too many arguments
            if len(all_args) > DEFAULT_MAX_ARGS:
                self.issues.append(_issue(
                    node.lineno, 1, "CPX001",
                    f"'{node.name}' has {len(all_args)} arguments (max {DEFAULT_MAX_ARGS}) — consider a config object or dataclass",
                    "WARNING", "complexity",
                ))

            # Function too long
            end = getattr(node, "end_lineno", None)
            if end:
                length = end - node.lineno
                if length > DEFAULT_MAX_FUNCTION_LINES:
                    self.issues.append(_issue(
                        node.lineno, 1, "CPX002",
                        f"'{node.name}' is {length} lines long (max {DEFAULT_MAX_FUNCTION_LINES}) — consider splitting",
                        "WARNING", "complexity",
                    ))

            # Too many return statements
            n_returns = sum(1 for n in ast.walk(node) if isinstance(n, ast.Return))
            if n_returns > DEFAULT_MAX_RETURNS:
                self.issues.append(_issue(
                    node.lineno, 1, "CPX004",
                    f"'{node.name}' has {n_returns} return statements (max {DEFAULT_MAX_RETURNS})",
                    "WARNING", "complexity",
                ))

            # Too many branches (cyclomatic complexity proxy)
            n_branches = sum(
                1 for n in ast.walk(node)
                if isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler, ast.With))
            )
            if n_branches > DEFAULT_MAX_BRANCHES:
                self.issues.append(_issue(
                    node.lineno, 1, "CPX005",
                    f"'{node.name}' has {n_branches} branches (max {DEFAULT_MAX_BRANCHES}) — high cyclomatic complexity",
                    "WARNING", "complexity",
                ))

        if "bugs" in self.active:
            # Mutable default arguments
            for default in args.defaults + [d for d in args.kw_defaults if d is not None]:
                if isinstance(default, MUTABLE_DEFAULT_TYPES):
                    kind = {ast.List: "list", ast.Dict: "dict", ast.Set: "set"}[type(default)]
                    self.issues.append(_issue(
                        node.lineno, 1, "BUG001",
                        f"Mutable default argument ({kind}) in '{node.name}' — "
                        "shared across all calls. Use None and initialise inside the function body",
                        "ERROR", "bugs",
                    ))

    # ── Nesting ───────────────────────────────────────────────────────────────

    def _enter_block(self, node: ast.AST) -> None:
        if "complexity" in self.active and self._nesting >= DEFAULT_MAX_NESTING:
            self.issues.append(_issue(
                node.lineno, 1, "CPX003",  # type: ignore[attr-defined]
                f"Code nested {self._nesting + 1} levels deep (max {DEFAULT_MAX_NESTING}) — extract to a function",
                "WARNING", "complexity",
            ))
        self._nesting += 1
        self.generic_visit(node)
        self._nesting -= 1

    def visit_For(self, node: ast.For) -> None:
        self._enter_block(node)

    def visit_While(self, node: ast.While) -> None:
        self._enter_block(node)

    def visit_If(self, node: ast.If) -> None:
        self._enter_block(node)

    def visit_With(self, node: ast.With) -> None:
        self._enter_block(node)

    # ── Import usage resolution ───────────────────────────────────────────────

    def resolve_unused_imports(self) -> list[dict]:
        if "imports" not in self.active:
            return []

        issues: list[dict] = []
        seen_locals: dict[str, int] = {}  # local_name → first line

        for imp in self._imports:
            local = imp["local"]

            # Duplicate import
            if local in seen_locals:
                issues.append(_issue(
                    imp["line"], 1, "IMP003",
                    f"'{local}' is imported again (first imported on line {seen_locals[local]})",
                    "WARNING", "imports",
                ))
            else:
                seen_locals[local] = imp["line"]

            # Unused import — check both direct usage and __all__ string exports
            used_in_code = local in self._used
            used_in_all = local in self._string_constants
            private = local.startswith("_")

            if not used_in_code and not used_in_all and not private:
                issues.append(_issue(
                    imp["line"], 1, "IMP001",
                    f"Unused import '{imp['name']}'" + (f" (imported as '{local}')" if local != imp["name"].split(".")[-1] else ""),
                    "WARNING", "imports",
                ))

        return issues


# ─── noqa suppression ─────────────────────────────────────────────────────────


def _apply_noqa(issues: list[dict], source: str) -> list[dict]:
    """Remove issues on lines that have a # noqa comment."""
    lines = source.split("\n")
    noqa_lines: dict[int, set[str] | None] = {}  # line_no → set of codes, or None = suppress all

    for i, line in enumerate(lines, 1):
        m = re.search(r"#\s*noqa(?::\s*([\w,\s]+))?", line, re.IGNORECASE)
        if m:
            codes_str = m.group(1)
            if codes_str:
                noqa_lines[i] = {c.strip().upper() for c in codes_str.split(",")}
            else:
                noqa_lines[i] = None  # suppress all

    filtered = []
    for issue in issues:
        ln = issue["line"]
        if ln in noqa_lines:
            suppressed = noqa_lines[ln]
            if suppressed is None or issue["code"] in suppressed:
                continue
        filtered.append(issue)
    return filtered


# ─── File linter ──────────────────────────────────────────────────────────────


def _lint_file(source: str, active: set[str], max_line_length: int) -> list[dict]:
    """Parse and lint a single Python source string; returns all issues after noqa filtering."""
    issues: list[dict] = []

    # Line-based style checks
    if "style" in active:
        issues.extend(_check_style_lines(source, max_line_length))

    # AST-based checks
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        issues.append(_issue(
            e.lineno or 1, e.offset or 1, "ERR001",
            f"Syntax error: {e.msg}",
            "ERROR", "bugs",
        ))
        return _apply_noqa(issues, source)

    analyzer = _Analyzer(active)
    analyzer.visit(tree)

    issues.extend(analyzer.issues)
    issues.extend(analyzer.resolve_unused_imports())

    return _apply_noqa(issues, source)


# ─── File discovery ───────────────────────────────────────────────────────────


def _iter_py_files(root: Path):
    """Recursively yield .py files under root, skipping directories in SKIP_DIRS."""
    for dirpath, dirnames, filenames in root.walk():
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


# ─── Entrypoint ───────────────────────────────────────────────────────────────


_DEFAULT_MAX_FINDINGS = 200
_LARGE_REPO_THRESHOLD = 50  # files — suggest splitting above this


def _int_param(params: dict, key: str, default: int) -> tuple[int, str | None]:
    """Safely coerce a params value to int; return (value, error_message_or_None)."""
    val = params.get(key, default)
    try:
        return int(val), None
    except (TypeError, ValueError):
        return default, f"Invalid value for '{key}': {val!r} — using default {default}"


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for python_lint_checker.

    Params:
        path            Path to a .py file or directory (default: ".")
        checks          Comma-separated categories or "all" (default: "all")
        max_line_length Max line length threshold (default: 88)
        max_findings    Cap on returned findings per run (default: 200)
        summary_only    If true, return counts only — no per-line findings (default: false)

    Returns {"result": {...}, "error": None} on success or {"result": None, "error": "..."} on failure.
    """
    path_str = params.get("path", ".")
    checks_param = params.get("checks", "all")

    max_line_length, err = _int_param(params, "max_line_length", DEFAULT_MAX_LINE_LENGTH)
    if err:
        return {"result": None, "error": err}
    max_findings, err = _int_param(params, "max_findings", _DEFAULT_MAX_FINDINGS)
    if err:
        return {"result": None, "error": err}
    summary_only = bool(params.get("summary_only", False))

    root = Path(path_str).expanduser().resolve()
    if not root.exists():
        return {"result": None, "error": f"Path does not exist: {path_str}"}

    # Parse active checks
    if checks_param == "all":
        active = ALL_CATEGORIES.copy()
    else:
        active = {c.strip() for c in checks_param.split(",")}
        unknown = active - ALL_CATEGORIES
        if unknown:
            return {
                "result": None,
                "error": f"Unknown check categories: {unknown}. Valid: {ALL_CATEGORIES}",
            }

    # Collect files
    if root.is_file():
        if root.suffix != ".py":
            return {"result": None, "error": "File must be a .py file"}
        py_files = [root]
        base = root.parent
    elif root.is_dir():
        py_files = sorted(_iter_py_files(root))
        base = root
    else:
        return {"result": None, "error": f"Path is neither a file nor a directory: {path_str}"}

    if not py_files:
        return {
            "result": {
                "path": str(root),
                "summary": {"files_scanned": 0, "files_with_issues": 0, "total_issues": 0,
                            "by_severity": {}, "by_category": {}},
                "findings": {},
            },
            "error": None,
        }

    # Suggest splitting if the repo is very large and summary_only wasn't set
    large_repo = root.is_dir() and len(py_files) > _LARGE_REPO_THRESHOLD
    split_hint: list[str] = []
    if large_repo and not summary_only:
        subdirs = sorted({p.relative_to(base).parts[0] for p in py_files if len(p.relative_to(base).parts) > 1})
        if subdirs:
            split_hint = [str(base / d) for d in subdirs]

    # Lint each file — stop adding to findings once max_findings is reached,
    # but continue scanning to produce accurate summary counts.
    all_findings: dict[str, list[dict]] = {}
    by_severity: dict[str, int] = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    by_category: dict[str, int] = {c: 0 for c in ALL_CATEGORIES}
    files_with_issues = 0
    total_issues = 0
    findings_capped = False

    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        issues = _lint_file(source, active, max_line_length)
        if not issues:
            continue

        issues.sort(key=lambda x: (x["line"], x["col"]))
        rel = str(py_file.relative_to(base)) if py_file != root else py_file.name
        files_with_issues += 1
        total_issues += len(issues)

        for issue in issues:
            by_severity[issue["severity"]] = by_severity.get(issue["severity"], 0) + 1
            by_category[issue["category"]] = by_category.get(issue["category"], 0) + 1

        # Only store findings up to the cap (or skip if summary_only)
        if not summary_only and not findings_capped:
            remaining = max_findings - sum(len(v) for v in all_findings.values())
            if remaining > 0:
                all_findings[rel] = issues[:remaining]
                if len(issues) > remaining:
                    findings_capped = True
            else:
                findings_capped = True

    result: dict[str, Any] = {
        "path": str(root),
        "summary": {
            "files_scanned": len(py_files),
            "files_with_issues": files_with_issues,
            "total_issues": total_issues,
            "by_severity": {k: v for k, v in by_severity.items() if v},
            "by_category": {k: v for k, v in by_category.items() if v},
        },
    }

    if not summary_only:
        result["findings"] = all_findings

    if findings_capped:
        result["truncated"] = True
        result["truncated_note"] = (
            f"Output capped at {max_findings} findings ({total_issues} total). "
            f"Use summary_only=true for counts only, or scan subdirectories individually."
        )

    if split_hint:
        result["split_suggestion"] = (
            f"Large repo ({len(py_files)} files). For focused results, scan subdirectories: "
            + ", ".join(f'"{p}"' for p in split_hint[:6])
        )

    return {"result": result, "error": None}
