"""
repo_scanner — scan a directory for leaked secrets, .gitignore gaps, and PII.

No external dependencies. Pure stdlib.
"""
import os
import re
from pathlib import Path
from typing import Any


# ─── Secret patterns ──────────────────────────────────────────────────────────

SECRET_PATTERNS = [
    {"name": "AWS Access Key ID", "regex": r"AKIA[0-9A-Z]{16}", "severity": "HIGH"},
    {
        "name": "AWS Secret Access Key",
        "regex": r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]",
        "severity": "HIGH",
    },
    {"name": "OpenAI API Key", "regex": r"sk-[a-zA-Z0-9]{48}", "severity": "HIGH"},
    {
        "name": "Anthropic API Key",
        "regex": r"sk-ant-[a-zA-Z0-9\-_]{90,}",
        "severity": "HIGH",
    },
    {
        "name": "GitHub Token",
        "regex": r"gh[pousr]_[A-Za-z0-9_]{36,255}",
        "severity": "HIGH",
    },
    {
        "name": "Private Key Block",
        "regex": r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY",
        "severity": "HIGH",
    },
    {
        "name": "Slack Token",
        "regex": r"xox[baprs]-[0-9A-Za-z\-]{10,}",
        "severity": "HIGH",
    },
    {
        "name": "Google API Key",
        "regex": r"AIza[0-9A-Za-z\-_]{35}",
        "severity": "HIGH",
    },
    {
        "name": "Database URL with credentials",
        "regex": r"(?i)(postgres|mysql|mongodb|redis):\/\/[^:]+:[^@\s]{3,}@",
        "severity": "HIGH",
    },
    {
        "name": "Generic API Key assignment",
        "regex": r"""(?i)(api_key|apikey|api[-_]secret|access[-_]key|secret[-_]key)\s*[:=]\s*['"][a-zA-Z0-9\-_]{16,}['"]""",
        "severity": "MEDIUM",
    },
    {
        "name": "Generic password assignment",
        "regex": r"""(?i)(password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}['"]""",
        "severity": "MEDIUM",
    },
    {
        "name": "Bearer token in code",
        "regex": r"(?i)bearer\s+[a-zA-Z0-9\-_\.]{20,}",
        "severity": "MEDIUM",
    },
    {
        "name": "JWT token",
        "regex": r"eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]+",
        "severity": "MEDIUM",
    },
]

# ─── PII patterns ─────────────────────────────────────────────────────────────

PII_PATTERNS = [
    {
        "name": "Email Address",
        "regex": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        "severity": "MEDIUM",
    },
    {
        "name": "US Social Security Number",
        "regex": r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
        "severity": "HIGH",
    },
    {
        "name": "Credit Card Number",
        "regex": r"(?<!\d)\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}(?!\d)",
        "severity": "HIGH",
    },
    {
        "name": "US Phone Number",
        "regex": r"(?<!\d)(\+1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}(?!\d)",
        "severity": "MEDIUM",
    },
    {
        "name": "Private IPv4 Address",
        "regex": r"(?<!\d)(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3})(?!\d)",
        "severity": "LOW",
    },
]

# ─── Gitignore: files and dirs that should always be ignored ──────────────────

SENSITIVE_FILES = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.staging",
    ".env.development",
    ".env.test",
    ".env.backup",
    "id_rsa",
    "id_ed25519",
    "id_dsa",
    "id_ecdsa",
    "credentials.json",
    "service-account.json",
    "secrets.yml",
    "secrets.yaml",
]

SENSITIVE_GLOBS = ["*.pem", "*.key", "*.p12", "*.pfx"]

SENSITIVE_DIRS = [
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".DS_Store",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
]

# ─── Scan helpers ─────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
}

SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mov", ".avi", ".mkv",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".parquet", ".pkl", ".bin", ".npy",
}

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB


def _redact(value: str) -> str:
    """Show the first 6 characters, redact everything after."""
    if len(value) <= 6:
        return "***[REDACTED]"
    return value[:6] + "***[REDACTED]"


def _should_skip(path: Path) -> bool:
    """Return True if the file should be excluded from scanning (binary, too large, skipped extension)."""
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return True
    except OSError:
        return True
    return False


def _iter_files(root: Path):
    """Recursively yield all file paths under root, skipping directories in SKIP_DIRS."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            yield Path(dirpath) / filename


def _parse_gitignore(root: Path) -> list[str]:
    gi = root / ".gitignore"
    if not gi.exists():
        return []
    lines = []
    for line in gi.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def _is_ignored(rel: str, patterns: list[str]) -> bool:
    """Best-effort check: does rel match any .gitignore pattern?"""
    name = Path(rel).name
    for pat in patterns:
        pat = pat.strip("/")
        # exact match on name or relative path
        if rel == pat or name == pat:
            return True
        # wildcard extension e.g. *.pem
        if pat.startswith("*") and rel.endswith(pat[1:]):
            return True
        # directory match  e.g. node_modules/
        if pat.endswith("/") and (rel == pat.rstrip("/") or rel.startswith(pat)):
            return True
        # partial path match
        if rel.endswith("/" + pat) or ("/" + pat + "/") in rel:
            return True
    return False


# ─── Checks ───────────────────────────────────────────────────────────────────


def scan_secrets(root: Path) -> list[dict]:
    """Scan all text files under root for leaked secrets using SECRET_PATTERNS."""
    findings: list[dict] = []
    for file_path in _iter_files(root):
        if _should_skip(file_path):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(file_path.relative_to(root))
        for pattern in SECRET_PATTERNS:
            for match in re.finditer(pattern["regex"], content):
                line_no = content[: match.start()].count("\n") + 1
                findings.append(
                    {
                        "file": rel,
                        "line": line_no,
                        "type": pattern["name"],
                        "severity": pattern["severity"],
                        "snippet": _redact(match.group()),
                    }
                )
    return findings


def scan_gitignore(root: Path) -> list[dict]:
    """Check for missing .gitignore entries covering sensitive files, globs, and directories."""
    findings: list[dict] = []
    patterns = _parse_gitignore(root)

    if not (root / ".gitignore").exists():
        findings.append(
            {
                "file": ".gitignore",
                "issue": ".gitignore does not exist — no files are protected from being committed",
                "severity": "HIGH",
            }
        )

    # Check sensitive named files
    for name in SENSITIVE_FILES:
        candidate = root / name
        if candidate.exists() and not _is_ignored(name, patterns):
            findings.append(
                {
                    "file": name,
                    "issue": "Sensitive file exists and is not covered by .gitignore",
                    "severity": "HIGH",
                }
            )

    # Check sensitive glob patterns (*.pem, *.key, etc.)
    for glob_pat in SENSITIVE_GLOBS:
        for match in root.rglob(glob_pat):
            rel = str(match.relative_to(root))
            if not _is_ignored(rel, patterns):
                findings.append(
                    {
                        "file": rel,
                        "issue": f"Matches {glob_pat} — should be in .gitignore",
                        "severity": "HIGH",
                    }
                )

    # Check sensitive directories
    for dir_name in SENSITIVE_DIRS:
        candidate = root / dir_name
        if candidate.is_dir() and not _is_ignored(dir_name, patterns):
            findings.append(
                {
                    "file": dir_name + "/",
                    "issue": "Directory should be covered by .gitignore",
                    "severity": "MEDIUM",
                }
            )

    return findings


def scan_pii(root: Path) -> list[dict]:
    """Scan data files (CSV, JSON, TXT, etc.) for PII patterns such as emails, SSNs, and credit cards."""
    findings: list[dict] = []
    data_extensions = {
        ".csv", ".tsv", ".json", ".jsonl",
        ".yml", ".yaml", ".xml",
        ".txt", ".log", ".sql", ".md",
    }
    for file_path in _iter_files(root):
        if file_path.suffix.lower() not in data_extensions:
            continue
        if _should_skip(file_path):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(file_path.relative_to(root))
        for pattern in PII_PATTERNS:
            matches = list(re.finditer(pattern["regex"], content))
            if not matches:
                continue
            # Report the first occurrence per pattern per file to keep output actionable
            first = matches[0]
            line_no = content[: first.start()].count("\n") + 1
            findings.append(
                {
                    "file": rel,
                    "line": line_no,
                    "type": pattern["name"],
                    "severity": pattern["severity"],
                    "occurrences_in_file": len(matches),
                }
            )
    return findings


# ─── Entrypoint ───────────────────────────────────────────────────────────────


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for repo_scanner.

    Params:
        path    Path to a directory to scan (default: ".")
        checks  Comma-separated checks or "all": secrets, gitignore, pii (default: "all")

    Returns {"result": {...}, "error": None} on success or {"result": None, "error": "..."} on failure.
    """
    path_str = params.get("path", ".")
    checks_param = params.get("checks", "all")

    root = Path(path_str).expanduser().resolve()

    if not root.exists():
        return {"result": None, "error": f"Path does not exist: {path_str}"}
    if not root.is_dir():
        return {"result": None, "error": f"Path is not a directory: {path_str}"}

    if checks_param == "all":
        checks = {"secrets", "gitignore", "pii"}
    else:
        checks = {c.strip() for c in checks_param.split(",")}

    unknown = checks - {"secrets", "gitignore", "pii"}
    if unknown:
        return {
            "result": None,
            "error": f"Unknown checks: {unknown}. Valid options: secrets, gitignore, pii",
        }

    result: dict[str, Any] = {
        "path": str(root),
        "summary": {"total_findings": 0, "secrets": 0, "gitignore_issues": 0, "pii": 0},
        "findings": {},
    }

    try:
        if "secrets" in checks:
            found = scan_secrets(root)
            result["findings"]["secrets"] = found
            result["summary"]["secrets"] = len(found)

        if "gitignore" in checks:
            found = scan_gitignore(root)
            result["findings"]["gitignore_issues"] = found
            result["summary"]["gitignore_issues"] = len(found)

        if "pii" in checks:
            found = scan_pii(root)
            result["findings"]["pii"] = found
            result["summary"]["pii"] = len(found)

        result["summary"]["total_findings"] = (
            result["summary"]["secrets"]
            + result["summary"]["gitignore_issues"]
            + result["summary"]["pii"]
        )

        return {"result": result, "error": None}

    except Exception as e:
        return {"result": None, "error": f"Scan failed: {e}"}
