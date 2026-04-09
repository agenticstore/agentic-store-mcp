import importlib.util
import tempfile
import os
from pathlib import Path

HANDLER = Path(__file__).parent / "handler.py"


def load():
    spec = importlib.util.spec_from_file_location("handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_log(lines: list[str], encoding: str = "utf-8") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding=encoding)
    f.write("\n".join(lines) + "\n")
    f.close()
    return f.name


def test_basic_tail():
    h = load()
    path = _make_log([f"line {i}" for i in range(100)])
    try:
        r = h.run({"path": path, "lines": 10})
        assert r["error"] is None
        assert len(r["result"]["lines"]) == 10
        assert r["result"]["lines"][-1] == "line 99"
    finally:
        os.unlink(path)


def test_fewer_lines_than_requested():
    h = load()
    path = _make_log(["alpha", "beta", "gamma"])
    try:
        r = h.run({"path": path, "lines": 50})
        assert r["error"] is None
        assert r["result"]["lines"] == ["alpha", "beta", "gamma"]
    finally:
        os.unlink(path)


def test_filter():
    h = load()
    path = _make_log(["INFO: started", "ERROR: failed", "INFO: ok", "ERROR: timeout"])
    try:
        r = h.run({"path": path, "lines": 100, "filter": "error"})
        assert r["error"] is None
        lines = r["result"]["lines"]
        assert all("error" in ln.lower() for ln in lines)
        assert len(lines) == 2
    finally:
        os.unlink(path)


def test_missing_file():
    h = load()
    r = h.run({"path": "/tmp/does_not_exist_xyz.log"})
    assert r["error"] is not None
    assert r["result"] is None


def test_missing_path_param():
    h = load()
    r = h.run({})
    assert r["error"] is not None


def test_max_lines_capped():
    h = load()
    path = _make_log(["x"] * 10)
    try:
        r = h.run({"path": path, "lines": 99999})
        assert r["error"] is None
        # lines param should be capped to _MAX_LINES (1000)
        assert r["result"]["requested_lines"] == 1000
    finally:
        os.unlink(path)


def test_directory_path_error():
    h = load()
    r = h.run({"path": "/tmp"})
    assert r["error"] is not None
