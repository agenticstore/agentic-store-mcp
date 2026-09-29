import importlib.util
from pathlib import Path

HANDLER = Path(__file__).parent / "handler.py"


def load():
    spec = importlib.util.spec_from_file_location("handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PYTHON_SAMPLE = '''\
# This is a top-level comment
"""Module docstring."""

import os
import sys  # unused

class Foo:
    """Foo class."""

    def bar(self, x):
        """Return x doubled."""
        # double it
        return x * 2

    def baz(self):
        pass
'''


def test_compress_python():
    h = load()
    r = h.run({"text": PYTHON_SAMPLE, "mode": "compress", "language": "python"})
    assert r["error"] is None
    out = r["result"]["output"]
    assert "docstring" not in out
    assert "# double it" not in out
    assert "def bar" in out
    assert r["result"]["compression_pct"] > 0


def test_summarize_python():
    h = load()
    r = h.run({"text": PYTHON_SAMPLE, "mode": "summarize", "language": "python"})
    assert r["error"] is None
    out = r["result"]["output"]
    assert "bar" in out or "Foo" in out


def test_both_mode():
    h = load()
    r = h.run({"text": PYTHON_SAMPLE, "mode": "both", "language": "python"})
    assert r["error"] is None
    assert "SUMMARY" in r["result"]["output"]


def test_auto_language_detect():
    h = load()
    r = h.run({"text": PYTHON_SAMPLE, "mode": "compress"})
    assert r["error"] is None
    assert r["result"]["language_detected"] == "python"


def test_empty_text_error():
    h = load()
    r = h.run({"text": ""})
    assert r["error"] is not None
    assert r["result"] is None


def test_invalid_mode():
    h = load()
    r = h.run({"text": "x = 1", "mode": "explode"})
    assert r["error"] is not None


def test_javascript_strip():
    h = load()
    js = "// header\nfunction foo() {\n  /* block */\n  return 1; // inline\n}"
    r = h.run({"text": js, "mode": "compress", "language": "javascript"})
    assert r["error"] is None
    assert "header" not in r["result"]["output"]
    assert "block" not in r["result"]["output"]
    assert "return 1" in r["result"]["output"]
