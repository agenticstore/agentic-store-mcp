import importlib.util
from pathlib import Path

HANDLER = Path(__file__).parent / "handler.py"


def load():
    spec = importlib.util.spec_from_file_location("handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_basic_relevance():
    h = load()
    items = [
        "src/auth/login.py",
        "src/database/migrations.py",
        "README.md",
        "src/auth/jwt_utils.py",
        "docs/design.md",
    ]
    r = h.run({"task": "Fix the JWT authentication login flow", "items": items, "keep_top_n": 2})
    assert r["error"] is None
    keep = r["result"]["keep"]
    # auth and jwt items should score higher
    assert any("auth" in str(k).lower() or "jwt" in str(k).lower() for k in keep)


def test_drop_irrelevant():
    h = load()
    items = ["auth/handler.py", "database/schema.sql", "styles/main.css"]
    r = h.run({"task": "Fix database migration failures", "items": items, "keep_top_n": 1})
    assert r["error"] is None
    # database item should be kept
    keep = r["result"]["keep"]
    assert any("database" in str(k).lower() or "schema" in str(k).lower() for k in keep)


def test_verbose_output():
    h = load()
    items = ["auth.py", "utils.py"]
    r = h.run({"task": "debug auth module", "items": items, "keep_top_n": 1, "verbose": True})
    assert r["error"] is None
    keep = r["result"]["keep"]
    assert isinstance(keep[0], dict)
    assert "score" in keep[0]
    assert "matched_keywords" in keep[0]


def test_missing_task():
    h = load()
    r = h.run({"task": "", "items": ["a.py"]})
    assert r["error"] is not None


def test_missing_items():
    h = load()
    r = h.run({"task": "fix auth", "items": []})
    assert r["error"] is not None


def test_all_relevant():
    """When all items are relevant, drop list should be empty."""
    h = load()
    items = ["auth_handler.py", "auth_utils.py", "auth_models.py"]
    r = h.run({"task": "refactor auth module authentication", "items": items, "keep_top_n": 10})
    assert r["error"] is None
    assert r["result"]["drop_count"] == 0
