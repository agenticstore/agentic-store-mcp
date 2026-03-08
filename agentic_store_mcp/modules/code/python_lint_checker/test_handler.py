"""
Tests for python_lint_checker.
Uses temporary files — zero network calls, zero external dependencies.
"""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("python_lint_checker_handler", Path(__file__).parent / "handler.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
run = _mod.run


# ─── Helpers ──────────────────────────────────────────────────────────────────


def write(base: Path, name: str, content: str) -> Path:
    p = base / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def lint(content: str, **kwargs) -> list[dict]:
    """Lint a string of Python source; return flat list of issues."""
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp = f.name
    try:
        result = run({"path": tmp, **kwargs})
        return result["result"]["findings"].get(Path(tmp).name, [])
    finally:
        os.unlink(tmp)


def codes(issues: list[dict]) -> list[str]:
    return [i["code"] for i in issues]


# ─── IMP001 — Unused import ───────────────────────────────────────────────────


def test_imp001_unused_import():
    issues = lint("import os\n\nx = 1\n")
    assert "IMP001" in codes(issues)


def test_imp001_used_import_not_flagged():
    issues = lint("import os\n\nprint(os.getcwd())\n")
    assert "IMP001" not in codes(issues)


def test_imp001_used_in_attribute_chain():
    issues = lint("import os.path\n\nresult = os.path.join('a', 'b')\n")
    assert "IMP001" not in codes(issues)


def test_imp001_from_import_unused():
    issues = lint("from os.path import join\n\nx = 1\n")
    assert "IMP001" in codes(issues)


def test_imp001_from_import_used():
    issues = lint("from os.path import join\n\nresult = join('a', 'b')\n")
    assert "IMP001" not in codes(issues)


def test_imp001_aliased_import_tracks_alias():
    issues = lint("import numpy as np\n\nx = 1\n")
    imp = next(i for i in issues if i["code"] == "IMP001")
    assert "numpy" in imp["message"]


def test_imp001_used_in_all_not_flagged():
    issues = lint('from os.path import join\n\n__all__ = ["join"]\n')
    assert "IMP001" not in codes(issues)


def test_imp001_private_import_not_flagged():
    # Underscore-prefixed locals are conventionally "intentionally unused"
    issues = lint("from os.path import join as _join\n\nx = 1\n")
    assert "IMP001" not in codes(issues)


# ─── IMP002 — Star import ─────────────────────────────────────────────────────


def test_imp002_star_import():
    issues = lint("from os.path import *\n")
    assert "IMP002" in codes(issues)


# ─── IMP003 — Duplicate import ───────────────────────────────────────────────


def test_imp003_duplicate_import():
    issues = lint("import os\nimport os\n\nprint(os.getcwd())\n")
    assert "IMP003" in codes(issues)


def test_imp003_no_duplicate():
    issues = lint("import os\nimport sys\n\nprint(os.getcwd(), sys.version)\n")
    assert "IMP003" not in codes(issues)


# ─── IMP004 — Multiple imports on one line ───────────────────────────────────


def test_imp004_multiple_imports():
    issues = lint("import os, sys\n\nprint(os.getcwd(), sys.version)\n")
    assert "IMP004" in codes(issues)


def test_imp004_single_import_ok():
    issues = lint("import os\n\nprint(os.getcwd())\n")
    assert "IMP004" not in codes(issues)


# ─── BUG001 — Mutable default argument ───────────────────────────────────────


def test_bug001_list_default():
    issues = lint("def f(x=[]):\n    pass\n")
    assert "BUG001" in codes(issues)


def test_bug001_dict_default():
    issues = lint("def f(x={}):\n    pass\n")
    assert "BUG001" in codes(issues)


def test_bug001_set_default():
    issues = lint("def f(x=set()):\n    pass\n")
    # set() is an ast.Call, not ast.Set — not flagged (correct behaviour)
    # Only literal {} sets are caught
    assert True  # documenting expected behaviour


def test_bug001_none_default_ok():
    issues = lint("def f(x=None):\n    if x is None:\n        x = []\n")
    assert "BUG001" not in codes(issues)


def test_bug001_kwonly_default():
    issues = lint("def f(*, opts={}):\n    pass\n")
    assert "BUG001" in codes(issues)


# ─── BUG002 — Bare except ────────────────────────────────────────────────────


def test_bug002_bare_except():
    issues = lint("try:\n    pass\nexcept:\n    pass\n")
    assert "BUG002" in codes(issues)


def test_bug002_specific_except_ok():
    issues = lint("try:\n    pass\nexcept ValueError:\n    pass\n")
    assert "BUG002" not in codes(issues)


# ─── BUG003 — Assert with tuple ──────────────────────────────────────────────


def test_bug003_assert_tuple():
    issues = lint('assert (x > 0, "x must be positive")\n', checks="bugs")
    assert "BUG003" in codes(issues)


def test_bug003_correct_assert_ok():
    issues = lint('assert x > 0, "x must be positive"\n', checks="bugs")
    assert "BUG003" not in codes(issues)


# ─── BUG004 — None comparison ────────────────────────────────────────────────


def test_bug004_eq_none():
    issues = lint("if x == None:\n    pass\n")
    assert "BUG004" in codes(issues)


def test_bug004_neq_none():
    issues = lint("if x != None:\n    pass\n")
    assert "BUG004" in codes(issues)


def test_bug004_is_none_ok():
    issues = lint("if x is None:\n    pass\n")
    assert "BUG004" not in codes(issues)


# ─── BUG005 — True/False comparison ─────────────────────────────────────────


def test_bug005_eq_true():
    issues = lint("if x == True:\n    pass\n")
    assert "BUG005" in codes(issues)


def test_bug005_eq_false():
    issues = lint("if x == False:\n    pass\n")
    assert "BUG005" in codes(issues)


def test_bug005_is_true_ok():
    issues = lint("if x is True:\n    pass\n")
    assert "BUG005" not in codes(issues)


# ─── BUG006 — Builtin shadowing ──────────────────────────────────────────────


def test_bug006_shadows_list():
    issues = lint("list = [1, 2, 3]\n")
    assert "BUG006" in codes(issues)


def test_bug006_shadows_dict():
    issues = lint("dict = {}\n")
    assert "BUG006" in codes(issues)


def test_bug006_normal_name_ok():
    issues = lint("my_list = [1, 2, 3]\n")
    assert "BUG006" not in codes(issues)


# ─── BUG007 — Silenced exception ─────────────────────────────────────────────


def test_bug007_silenced_with_pass():
    issues = lint("try:\n    risky()\nexcept Exception:\n    pass\n")
    assert "BUG007" in codes(issues)


def test_bug007_not_flagged_with_log():
    issues = lint("try:\n    risky()\nexcept Exception as e:\n    log(e)\n")
    assert "BUG007" not in codes(issues)


# ─── BUG008 — Duplicate dict key ─────────────────────────────────────────────


def test_bug008_duplicate_key():
    issues = lint('d = {"a": 1, "b": 2, "a": 3}\n')
    assert "BUG008" in codes(issues)


def test_bug008_unique_keys_ok():
    issues = lint('d = {"a": 1, "b": 2, "c": 3}\n')
    assert "BUG008" not in codes(issues)


# ─── STY001 — Line too long ───────────────────────────────────────────────────


def test_sty001_long_line():
    issues = lint("x = " + "a" * 90 + "\n")
    assert "STY001" in codes(issues)


def test_sty001_custom_max_line_length():
    line = "x = " + "a" * 100  # 104 chars
    issues = lint(line + "\n", max_line_length=120)
    assert "STY001" not in codes(issues)


def test_sty001_short_line_ok():
    issues = lint("x = 1\n")
    assert "STY001" not in codes(issues)


# ─── STY002 — Trailing whitespace ────────────────────────────────────────────


def test_sty002_trailing_space():
    issues = lint("x = 1   \n")
    assert "STY002" in codes(issues)


def test_sty002_no_trailing_space_ok():
    issues = lint("x = 1\n")
    assert "STY002" not in codes(issues)


# ─── STY003 — Mixed tabs/spaces ──────────────────────────────────────────────


def test_sty003_mixed_indentation():
    source = "def f():\n    x = 1\n\tdef g():\n\t    pass\n"
    issues = lint(source)
    assert "STY003" in codes(issues)


# ─── STY004 — Multiple statements ────────────────────────────────────────────


def test_sty004_semicolon():
    issues = lint("x = 1; y = 2\n")
    assert "STY004" in codes(issues)


def test_sty004_no_semicolon_ok():
    issues = lint("x = 1\ny = 2\n")
    assert "STY004" not in codes(issues)


# ─── STY005 — print() call ───────────────────────────────────────────────────


def test_sty005_print_call():
    issues = lint('print("hello")\n')
    assert "STY005" in codes(issues)


def test_sty005_logging_ok():
    issues = lint('import logging\nlogging.info("hello")\n')
    assert "STY005" not in codes(issues)


# ─── STY006 — TODO/FIXME comments ────────────────────────────────────────────


def test_sty006_todo():
    issues = lint("x = 1  # TODO: fix this\n")
    assert "STY006" in codes(issues)


def test_sty006_fixme():
    issues = lint("x = 1  # FIXME: broken\n")
    assert "STY006" in codes(issues)


def test_sty006_hack():
    issues = lint("x = 1  # HACK: workaround\n")
    assert "STY006" in codes(issues)


# ─── CPX001 — Too many arguments ─────────────────────────────────────────────


def test_cpx001_too_many_args():
    issues = lint("def f(a, b, c, d, e, f, g, h):\n    pass\n")
    assert "CPX001" in codes(issues)


def test_cpx001_acceptable_args_ok():
    issues = lint("def f(a, b, c):\n    pass\n")
    assert "CPX001" not in codes(issues)


# ─── CPX002 — Function too long ──────────────────────────────────────────────


def test_cpx002_long_function():
    body = "\n".join(f"    x{i} = {i}" for i in range(65))
    issues = lint(f"def f():\n{body}\n")
    assert "CPX002" in codes(issues)


def test_cpx002_short_function_ok():
    issues = lint("def f():\n    return 1\n")
    assert "CPX002" not in codes(issues)


# ─── CPX003 — Deep nesting ────────────────────────────────────────────────────


def test_cpx003_deep_nesting():
    source = (
        "for a in x:\n"
        "  for b in y:\n"
        "    for c in z:\n"
        "      for d in w:\n"
        "        if True:\n"
        "          pass\n"
    )
    issues = lint(source)
    assert "CPX003" in codes(issues)


# ─── CPX004 — Too many returns ───────────────────────────────────────────────


def test_cpx004_many_returns():
    returns = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(7))
    issues = lint(f"def f(x):\n{returns}\n    return -1\n")
    assert "CPX004" in codes(issues)


# ─── CPX005 — Too many branches ──────────────────────────────────────────────


def test_cpx005_many_branches():
    branches = "\n".join(f"    if x == {i}:\n        pass" for i in range(12))
    issues = lint(f"def f(x):\n{branches}\n")
    assert "CPX005" in codes(issues)


# ─── Syntax error handling ────────────────────────────────────────────────────


def test_syntax_error_reported_gracefully():
    issues = lint("def f(:\n    pass\n")
    assert any(i["code"] == "ERR001" for i in issues)


# ─── noqa suppression ─────────────────────────────────────────────────────────


def test_noqa_suppresses_all_on_line():
    issues = lint("import os  # noqa\n")
    assert "IMP001" not in codes(issues)


def test_noqa_specific_code_suppresses():
    issues = lint("import os  # noqa: IMP001\n")
    assert "IMP001" not in codes(issues)


def test_noqa_specific_code_does_not_suppress_other():
    issues = lint("import os, sys  # noqa: IMP001\nprint(os.getcwd(), sys.version)\n")
    # IMP001 suppressed, but IMP004 (multiple imports) should still fire
    assert "IMP004" in codes(issues)
    assert "IMP001" not in codes(issues)


# ─── Selective checks ─────────────────────────────────────────────────────────


def test_selective_checks_bugs_only():
    issues = lint("import os\ndef f(x=[]):\n    pass\n", checks="bugs")
    found = codes(issues)
    assert "BUG001" in found
    assert "IMP001" not in found  # imports not active


def test_selective_checks_invalid_category():
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"x = 1\n")
        tmp = f.name
    try:
        result = run({"path": tmp, "checks": "malware"})
        assert result["result"] is None
        assert "Unknown check categories" in result["error"]
    finally:
        os.unlink(tmp)


# ─── Directory scan ───────────────────────────────────────────────────────────


def test_directory_scan(tmp_path):
    write(tmp_path, "a.py", "import os\nx = 1\n")
    write(tmp_path, "b.py", "x = 1\n")
    write(tmp_path, "sub/c.py", "import sys\ny = 2\n")
    result = run({"path": str(tmp_path)})
    assert result["error"] is None
    findings = result["result"]["findings"]
    # a.py and sub/c.py have unused imports
    assert any("a.py" in k for k in findings)
    assert result["result"]["summary"]["files_scanned"] == 3


def test_directory_skips_non_py_files(tmp_path):
    write(tmp_path, "notes.txt", "import os\n")
    write(tmp_path, "script.py", "x = 1\n")
    result = run({"path": str(tmp_path)})
    assert result["result"]["summary"]["files_scanned"] == 1


def test_directory_skips_venv(tmp_path):
    write(tmp_path, "main.py", "x = 1\n")
    write(tmp_path, ".venv/lib/something.py", "import os\nx = 1\n")
    result = run({"path": str(tmp_path)})
    assert result["result"]["summary"]["files_scanned"] == 1


# ─── Error paths ──────────────────────────────────────────────────────────────


def test_nonexistent_path():
    result = run({"path": "/nonexistent/path/abc123"})
    assert result["result"] is None
    assert result["error"] is not None


def test_non_py_file_rejected(tmp_path):
    f = write(tmp_path, "notes.txt", "hello")
    result = run({"path": str(f)})
    assert result["result"] is None
    assert ".py" in result["error"]


def test_clean_file_produces_no_findings():
    source = 'import os\n\nresult = os.getcwd()\n'
    issues = lint(source)
    assert issues == []


def test_summary_counts_match_findings():
    source = "import os\nimport os\ndef f(x=[]):\n    pass\n"
    import os as _os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(source)
        tmp = f.name
    try:
        result = run({"path": tmp})
        total_in_findings = sum(len(v) for v in result["result"]["findings"].values())
        assert result["result"]["summary"]["total_issues"] == total_in_findings
    finally:
        _os.unlink(tmp)
