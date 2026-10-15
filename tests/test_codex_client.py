import shutil
import tomllib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agentic_store_mcp.webapp import config_writer
from agentic_store_mcp.webapp.app import app


def test_gpt_in_clients_list(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    client = next(
        c
        for c in TestClient(app).get("/api/clients").json()["clients"]
        if c["slug"] == "codex"
    )
    assert client["name"] == "GPT / OpenAI Codex"
    assert client["config_path"] == str(tmp_path / "config.toml")


@pytest.mark.skipif(not shutil.which("codex"), reason="Codex CLI not installed")
def test_apply_uses_real_codex_toml_editor(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    target = tmp_path / "config.toml"
    target.write_text(
        '# keep comment\nmodel = "user-choice"\n[mcp_servers.node_repl]\ncommand = "node"\nargs = ["--user-setting"]\n[mcp_servers.other]\ncommand = "other-server"\n'
    )
    for _ in range(2):
        response = TestClient(app).post(
            "/api/apply", json={"client": "codex", "enabled_tools": ["repo_scanner"]}
        )
        assert response.status_code == 200, response.text
        text = target.read_text()
        parsed = tomllib.loads(text)
        assert "# keep comment" in text
        assert parsed["model"] == "user-choice"
        assert parsed["mcp_servers"]["node_repl"]["args"] == ["--user-setting"]
        assert parsed["mcp_servers"]["other"]["command"] == "other-server"
        entry = parsed["mcp_servers"]["agentic-store-mcp"]
        assert entry["args"][-2:] == ["--tools", "repo_scanner"]
        assert entry["command"]


def test_invalid_toml_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    target = tmp_path / "config.toml"
    target.write_text("invalid = [")
    with patch.object(config_writer.shutil, "which", return_value="/codex"):
        assert not config_writer.write_config("codex", None)["ok"]
    assert target.read_text() == "invalid = ["


def test_missing_codex_no_write(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    with patch.object(config_writer.shutil, "which", return_value=None):
        result = config_writer.write_config("codex", None)
    assert not result["ok"] and "Install the Codex CLI" in result["error"]
    assert not (tmp_path / "config.toml").exists()
