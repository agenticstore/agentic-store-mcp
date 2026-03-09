"""Tests for tool_search."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

HANDLER = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("tool_search_handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_fake_modules(tmp_path: Path) -> Path:
    """Build a minimal fake modules/ directory for testing."""
    modules = tmp_path / "modules"

    # 2-level tool: data/web_search
    data = modules / "data" / "web_search"
    data.mkdir(parents=True)
    (data / "handler.py").write_text("def run(p): return {}")
    (data / "schema.json").write_text(json.dumps({
        "name": "web_search",
        "description": "Search the web for information. Local cache supported.",
        "connectors": [],
        "inputSchema": {"type": "object", "properties": {}},
    }))

    # 3-level tool: code/security/repo_scanner
    scanner = modules / "code" / "security" / "repo_scanner"
    scanner.mkdir(parents=True)
    (scanner / "handler.py").write_text("def run(p): return {}")
    (scanner / "schema.json").write_text(json.dumps({
        "name": "repo_scanner",
        "description": "Scans local directory for leaked secrets and PII.",
        "connectors": [],
        "inputSchema": {"type": "object", "properties": {}},
    }))

    # 3-level tool: code/remote_integrations/manage_issue (write + api)
    issue = modules / "code" / "remote_integrations" / "manage_issue"
    issue.mkdir(parents=True)
    (issue / "handler.py").write_text("def run(p): return {}")
    (issue / "schema.json").write_text(json.dumps({
        "name": "manage_issue",
        "description": "Creates or updates GitHub issues.",
        "connectors": ["github"],
        "inputSchema": {
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
        },
    }))

    # 3-level tool: code/codebase_analysis/get_file (api, read)
    get_file = modules / "code" / "codebase_analysis" / "get_file"
    get_file.mkdir(parents=True)
    (get_file / "handler.py").write_text("def run(p): return {}")
    (get_file / "schema.json").write_text(json.dumps({
        "name": "get_file",
        "description": "Fetches file content from a GitHub repository.",
        "connectors": ["github"],
        "inputSchema": {"type": "object", "properties": {}},
    }))

    return modules


# ─── Discovery ────────────────────────────────────────────────────────────────

def test_discovers_all_tools(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({})

    assert result["error"] is None
    assert result["result"]["total"] == 4
    names = {t["name"] for t in result["result"]["tools"]}
    assert names == {"web_search", "repo_scanner", "manage_issue", "get_file"}


def test_discovers_2_and_3_level(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({})

    tools = {t["name"]: t for t in result["result"]["tools"]}

    # 2-level tool has no submodule
    assert tools["web_search"]["submodule"] is None
    assert tools["web_search"]["module"] == "data"

    # 3-level tool has submodule
    assert tools["repo_scanner"]["submodule"] == "security"
    assert tools["repo_scanner"]["module"] == "code"


# ─── Tag inference ────────────────────────────────────────────────────────────

def test_tags_api_required(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({})

    tools = {t["name"]: t for t in result["result"]["tools"]}
    assert "api_required" in tools["manage_issue"]["tags"]
    assert "api_required" in tools["get_file"]["tags"]
    assert "api_required" not in tools["repo_scanner"]["tags"]


def test_tags_local_only(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({})

    tools = {t["name"]: t for t in result["result"]["tools"]}
    assert "local_only" in tools["repo_scanner"]["tags"]


def test_tags_write_tool(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({})

    tools = {t["name"]: t for t in result["result"]["tools"]}
    # manage_issue has "confirmed" param → write_tool
    assert "write_tool" in tools["manage_issue"]["tags"]
    # get_file has no confirmed + no write keywords → read_only
    assert "read_only" in tools["get_file"]["tags"]
    assert "write_tool" not in tools["get_file"]["tags"]


# ─── Filtering ────────────────────────────────────────────────────────────────

def test_filter_by_query(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({"query": "github"})

    assert result["error"] is None
    names = {t["name"] for t in result["result"]["tools"]}
    assert "manage_issue" in names
    assert "get_file" in names
    assert "repo_scanner" not in names


def test_filter_by_module(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({"module": "data"})

    assert result["error"] is None
    assert result["result"]["total"] == 1
    assert result["result"]["tools"][0]["name"] == "web_search"


def test_filter_by_tag_api_required(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({"tags": "api_required"})

    assert result["error"] is None
    names = {t["name"] for t in result["result"]["tools"]}
    assert names == {"manage_issue", "get_file"}


def test_filter_by_tag_read_only(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({"tags": "read_only"})

    names = {t["name"] for t in result["result"]["tools"]}
    assert "manage_issue" not in names


def test_combined_filters(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({"module": "code", "tags": "api_required,read_only"})

    assert result["error"] is None
    # Only get_file: code module + api_required + read_only
    names = {t["name"] for t in result["result"]["tools"]}
    assert names == {"get_file"}


def test_invalid_tag():
    handler = load_handler()
    result = handler.run({"tags": "nonexistent_tag"})
    assert result["error"] is not None
    assert "Unknown tag" in result["error"]


def test_empty_query_returns_all(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({"query": ""})

    assert result["result"]["total"] == 4


def test_no_match_returns_empty(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({"query": "zzz_no_such_tool_xyz"})

    assert result["error"] is None
    assert result["result"]["total"] == 0


def test_runs_against_real_modules():
    """Smoke test against the actual modules/ directory."""
    handler = load_handler()
    result = handler.run({})
    assert result["error"] is None
    assert result["result"]["total"] >= 21  # all current tools
    names = {t["name"] for t in result["result"]["tools"]}
    assert "repo_scanner" in names
    assert "manage_issue" in names
    assert "tool_search" in names


def test_tag_summary_structure(tmp_path):
    handler = load_handler()
    fake_modules = _make_fake_modules(tmp_path)

    with patch.object(handler, "MODULES_DIR", fake_modules):
        result = handler.run({})

    summary = result["result"]["tag_summary"]
    assert isinstance(summary, dict)
    assert "api_required" in summary
    assert summary["api_required"] == 2  # manage_issue + get_file
