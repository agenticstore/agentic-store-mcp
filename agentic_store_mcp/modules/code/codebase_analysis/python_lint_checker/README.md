# python_lint_checker

> Analyzes Python files for unused imports, likely bugs, style violations, and complexity issues. No code execution — pure static analysis.

Walks Python source files using the built-in `ast` module and line-by-line heuristics. Zero external dependencies. Scan a single file or an entire directory tree in one call.

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | Yes | Python file or directory to analyze. Example: `"/Users/me/project/src"` |
| `checks` | `string` | No | Comma-separated categories: `imports`, `bugs`, `style`, `complexity`. Default: `"all"` |
| `max_line_length` | `integer` | No | Line length threshold for STY001. Default: `88` (matches black/ruff) |

## Required Setup

No API keys required. Uses only Python's standard library (`ast`, `re`, `pathlib`).

## Check Categories

### `imports`

| Code | Severity | What it flags |
|------|----------|---------------|
| IMP001 | WARNING | Unused import — name never referenced in the file |
| IMP002 | WARNING | `from x import *` — imports everything into scope |
| IMP003 | WARNING | Same name imported more than once |
| IMP004 | WARNING | `import os, sys` — multiple imports on one line |

### `bugs`

| Code | Severity | What it flags |
|------|----------|---------------|
| BUG001 | ERROR | Mutable default argument (`def f(x=[])`) — shared across all calls |
| BUG002 | WARNING | Bare `except:` — catches SystemExit and KeyboardInterrupt |
| BUG003 | ERROR | `assert (condition, msg)` — tuple is always truthy, assertion never fails |
| BUG004 | WARNING | `x == None` — use `x is None` |
| BUG005 | WARNING | `x == True` — use `x is True` or the boolean directly |
| BUG006 | WARNING | Variable shadows a Python builtin (`list = []`, `dict = {}`) |
| BUG007 | WARNING | Exception caught and silenced with `pass` |
| BUG008 | ERROR | Duplicate key in dict literal — earlier value silently overwritten |

### `style`

| Code | Severity | What it flags |
|------|----------|---------------|
| STY001 | WARNING | Line exceeds `max_line_length` characters |
| STY002 | WARNING | Trailing whitespace |
| STY003 | ERROR | Mixed tabs and spaces for indentation |
| STY004 | WARNING | Multiple statements on one line (semicolon) |
| STY005 | INFO | `print()` call — consider `logging` for production code |
| STY006 | INFO | TODO / FIXME / HACK / XXX comment |

### `complexity`

| Code | Severity | What it flags |
|------|----------|---------------|
| CPX001 | WARNING | Function has more than 7 arguments |
| CPX002 | WARNING | Function body exceeds 60 lines |
| CPX003 | WARNING | Code nested more than 4 levels deep |
| CPX004 | WARNING | Function has more than 5 return statements |
| CPX005 | WARNING | Function has more than 10 branches (cyclomatic complexity) |

## noqa Support

Suppress specific issues on a line with an inline comment:

```python
import os  # noqa             — suppress all issues on this line
import os  # noqa: IMP001    — suppress only IMP001
import os  # noqa: IMP001, IMP003
```

## Examples

### Example 1: Scan a project directory

Input:
```json
{
  "path": "/Users/me/my-project/src"
}
```

Output:
```json
{
  "path": "/Users/me/my-project/src",
  "summary": {
    "files_scanned": 12,
    "files_with_issues": 4,
    "total_issues": 9,
    "by_severity": { "ERROR": 2, "WARNING": 6, "INFO": 1 },
    "by_category": { "imports": 3, "bugs": 4, "style": 2 }
  },
  "findings": {
    "api/client.py": [
      {
        "line": 3,
        "col": 1,
        "code": "IMP001",
        "message": "Unused import 'json'",
        "severity": "WARNING",
        "category": "imports"
      },
      {
        "line": 18,
        "col": 1,
        "code": "BUG001",
        "message": "Mutable default argument (list) in 'fetch_all' — shared across all calls. Use None and initialise inside the function body",
        "severity": "ERROR",
        "category": "bugs"
      }
    ]
  }
}
```

### Example 2: Bugs only, single file

Input:
```json
{
  "path": "/Users/me/project/utils.py",
  "checks": "bugs"
}
```

### Example 3: Relax line length for a project using 120-char lines

Input:
```json
{
  "path": "/Users/me/project",
  "max_line_length": 120
}
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Path does not exist` | Typo in path | Use an absolute path |
| `File must be a .py file` | Passed a non-Python file | Point to a `.py` file or a directory |
| `Unknown check categories` | Typo in `checks` param | Valid values: `imports`, `bugs`, `style`, `complexity` |
| `ERR001` in findings | Syntax error in the file | Fix the syntax error — AST-based checks can't run on unparseable files |
| IMP001 false positive for `__all__` | Name exported via string in `__all__` | Tool checks string constants — make sure the name matches exactly |

## Known Limitations

- **Unused imports**: detects direct name usage only. Dynamic access via `getattr(module, name)` is not tracked.
- **Type annotations with `from __future__ import annotations`**: annotations become strings at runtime; names used only in string-form annotations may be reported as unused.
- **Complexity thresholds are global**: there is no per-function or per-file override (use `# noqa` for exceptions).
- **C extensions and `.pyi` stubs**: only `.py` files are scanned.
- **No auto-fix**: this tool reports issues — it does not modify files.
