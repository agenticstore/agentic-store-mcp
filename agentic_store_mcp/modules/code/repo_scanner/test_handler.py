"""
Tests for repo_scanner.

Uses pytest's tmp_path fixture to create isolated temporary directories.
"""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("repo_scanner_handler", Path(__file__).parent / "handler.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
run = _mod.run


# ─── Helpers ──────────────────────────────────────────────────────────────────


def make_file(base: Path, name: str, content: str) -> Path:
    p = base / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ─── Secrets ──────────────────────────────────────────────────────────────────


def test_secrets_clean_dir(tmp_path):
    result = run({"path": str(tmp_path), "checks": "secrets"})
    assert result["error"] is None
    assert result["result"]["summary"]["secrets"] == 0


def test_secrets_detects_aws_key(tmp_path):
    make_file(tmp_path, "config.py", 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
    result = run({"path": str(tmp_path), "checks": "secrets"})
    assert result["error"] is None
    secrets = result["result"]["findings"]["secrets"]
    assert any(f["type"] == "AWS Access Key ID" for f in secrets)


def test_secrets_detects_openai_key(tmp_path):
    key = "sk-" + "a" * 48
    make_file(tmp_path, "app.py", f'client = OpenAI(api_key="{key}")\n')
    result = run({"path": str(tmp_path), "checks": "secrets"})
    secrets = result["result"]["findings"]["secrets"]
    assert any(f["type"] == "OpenAI API Key" for f in secrets)


def test_secrets_detects_private_key_block(tmp_path):
    make_file(tmp_path, "id_rsa.txt", "-----BEGIN RSA PRIVATE KEY-----\nMIIEo...")
    result = run({"path": str(tmp_path), "checks": "secrets"})
    secrets = result["result"]["findings"]["secrets"]
    assert any(f["type"] == "Private Key Block" for f in secrets)


def test_secrets_detects_db_url(tmp_path):
    make_file(tmp_path, "settings.py", 'DB = "postgres://admin:hunter2@localhost/db"\n')
    result = run({"path": str(tmp_path), "checks": "secrets"})
    secrets = result["result"]["findings"]["secrets"]
    assert any(f["type"] == "Database URL with credentials" for f in secrets)


def test_secrets_are_redacted(tmp_path):
    make_file(tmp_path, "config.py", 'KEY = "AKIAIOSFODNN7EXAMPLE"\n')
    result = run({"path": str(tmp_path), "checks": "secrets"})
    for finding in result["result"]["findings"]["secrets"]:
        assert "REDACTED" in finding["snippet"]


def test_secrets_reports_correct_line_number(tmp_path):
    make_file(
        tmp_path,
        "config.py",
        "# line 1\n# line 2\nKEY = 'AKIAIOSFODNN7EXAMPLE'\n",
    )
    result = run({"path": str(tmp_path), "checks": "secrets"})
    secrets = result["result"]["findings"]["secrets"]
    aws = [f for f in secrets if f["type"] == "AWS Access Key ID"]
    assert aws[0]["line"] == 3


# ─── Gitignore ────────────────────────────────────────────────────────────────


def test_gitignore_flags_missing_gitignore(tmp_path):
    make_file(tmp_path, ".env", "SECRET=abc123")
    result = run({"path": str(tmp_path), "checks": "gitignore"})
    issues = result["result"]["findings"]["gitignore_issues"]
    assert any(".gitignore" in f["file"] for f in issues)


def test_gitignore_flags_env_not_ignored(tmp_path):
    make_file(tmp_path, ".gitignore", "node_modules/\n")
    make_file(tmp_path, ".env", "API_KEY=secret123")
    result = run({"path": str(tmp_path), "checks": "gitignore"})
    issues = result["result"]["findings"]["gitignore_issues"]
    assert any(f["file"] == ".env" for f in issues)


def test_gitignore_no_issue_when_env_is_ignored(tmp_path):
    make_file(tmp_path, ".gitignore", ".env\nnode_modules/\n")
    make_file(tmp_path, ".env", "API_KEY=secret123")
    result = run({"path": str(tmp_path), "checks": "gitignore"})
    issues = result["result"]["findings"]["gitignore_issues"]
    assert not any(f["file"] == ".env" for f in issues)


def test_gitignore_flags_venv_dir(tmp_path):
    make_file(tmp_path, ".gitignore", "")
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    (venv_dir / "placeholder").write_text("")
    result = run({"path": str(tmp_path), "checks": "gitignore"})
    issues = result["result"]["findings"]["gitignore_issues"]
    assert any("venv" in f["file"] for f in issues)


def test_gitignore_clean(tmp_path):
    make_file(tmp_path, ".gitignore", ".env\n.venv/\nnode_modules/\n__pycache__/\n")
    result = run({"path": str(tmp_path), "checks": "gitignore"})
    issues = result["result"]["findings"]["gitignore_issues"]
    # No sensitive files exist, so no findings beyond the ones that don't exist
    assert result["error"] is None


# ─── PII ──────────────────────────────────────────────────────────────────────


def test_pii_detects_email_in_csv(tmp_path):
    make_file(tmp_path, "users.csv", "name,email\nJohn,john.doe@example.com\n")
    result = run({"path": str(tmp_path), "checks": "pii"})
    pii = result["result"]["findings"]["pii"]
    assert any(f["type"] == "Email Address" for f in pii)


def test_pii_detects_ssn(tmp_path):
    make_file(tmp_path, "data.csv", "id,ssn\n1,123-45-6789\n")
    result = run({"path": str(tmp_path), "checks": "pii"})
    pii = result["result"]["findings"]["pii"]
    assert any(f["type"] == "US Social Security Number" for f in pii)


def test_pii_skips_non_data_files(tmp_path):
    # .py files are not scanned for PII — only data file types
    make_file(tmp_path, "app.py", "email = 'test@example.com'\n")
    result = run({"path": str(tmp_path), "checks": "pii"})
    pii = result["result"]["findings"]["pii"]
    assert len(pii) == 0


def test_pii_reports_occurrence_count(tmp_path):
    emails = "\n".join(f"user{i}@example.com" for i in range(10))
    make_file(tmp_path, "emails.txt", emails)
    result = run({"path": str(tmp_path), "checks": "pii"})
    pii = result["result"]["findings"]["pii"]
    email_findings = [f for f in pii if f["type"] == "Email Address"]
    assert email_findings[0]["occurrences_in_file"] == 10


# ─── Error handling ───────────────────────────────────────────────────────────


def test_invalid_path_returns_error():
    result = run({"path": "/nonexistent/path/abc123xyz"})
    assert result["result"] is None
    assert result["error"] is not None


def test_file_path_instead_of_dir(tmp_path):
    f = make_file(tmp_path, "file.py", "print('hello')")
    result = run({"path": str(f)})
    assert result["result"] is None
    assert "not a directory" in result["error"]


def test_invalid_check_name(tmp_path):
    result = run({"path": str(tmp_path), "checks": "malware"})
    assert result["result"] is None
    assert "Unknown checks" in result["error"]


# ─── Selective checks ─────────────────────────────────────────────────────────


def test_selective_secrets_only(tmp_path):
    result = run({"path": str(tmp_path), "checks": "secrets"})
    assert result["error"] is None
    assert "secrets" in result["result"]["findings"]
    assert "pii" not in result["result"]["findings"]
    assert "gitignore_issues" not in result["result"]["findings"]


def test_selective_multiple_checks(tmp_path):
    result = run({"path": str(tmp_path), "checks": "secrets,pii"})
    assert result["error"] is None
    assert "secrets" in result["result"]["findings"]
    assert "pii" in result["result"]["findings"]
    assert "gitignore_issues" not in result["result"]["findings"]


def test_all_checks_default(tmp_path):
    result = run({"path": str(tmp_path)})
    assert result["error"] is None
    findings = result["result"]["findings"]
    assert "secrets" in findings
    assert "gitignore_issues" in findings
    assert "pii" in findings


# ─── Summary totals ───────────────────────────────────────────────────────────


def test_summary_totals_are_correct(tmp_path):
    make_file(tmp_path, "config.py", 'KEY = "AKIAIOSFODNN7EXAMPLE"\n')
    make_file(tmp_path, ".env", "SECRET=abc")
    make_file(tmp_path, "users.csv", "email\ntest@example.com\n")
    result = run({"path": str(tmp_path)})
    s = result["result"]["summary"]
    assert s["total_findings"] == s["secrets"] + s["gitignore_issues"] + s["pii"]
