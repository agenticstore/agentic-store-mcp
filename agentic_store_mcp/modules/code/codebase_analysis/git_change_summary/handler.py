"""Summarize repository changes without modifying the working tree."""
from __future__ import annotations
import re, subprocess
from pathlib import Path
from typing import Any

def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=15, check=False)
    if result.returncode: raise ValueError(result.stderr.strip() or "Git command failed")
    return result.stdout

def run(args: dict[str, Any]) -> dict[str, Any]:
    root = Path(args.get("path", ".")).expanduser().resolve()
    if not (root / ".git").exists(): raise ValueError("'path' must be a Git repository")
    max_chars = min(max(int(args.get("max_diff_chars", 12_000)), 500), 50_000)
    status = _git(root, "status", "--porcelain=v1").splitlines()
    staged = [line[3:] for line in status if line[:2].strip() and line[0] not in " ?"]
    unstaged = [line[3:] for line in status if len(line) > 3 and line[1] not in " ?"]
    diff = _git(root, "diff", "--no-ext-diff", "--unified=2")
    cached = _git(root, "diff", "--cached", "--no-ext-diff", "--unified=2")
    numstat = _git(root, "diff", "--numstat") + _git(root, "diff", "--cached", "--numstat")
    files = []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) == 3: files.append({"path": parts[2], "added": parts[0], "deleted": parts[1]})
    generated = [item["path"] for item in files if re.search(r"(^|/)(dist|build|coverage)/|\.min\.|\.map$|\.lock$|\.generated\.", item["path"], re.I)]
    symbol_pattern = re.compile(r"^[+ ](?:def|class|function|export\s+(?:class|function|const)|interface|type)\s+([\w$]+)", re.M)
    symbols = sorted(set(symbol_pattern.findall(diff + "\n" + cached)))[:100]
    combined = ("# Unstaged\n" + diff + "\n# Staged\n" + cached)
    return {"read_only": True, "branch": _git(root, "branch", "--show-current").strip(), "staged_files": staged, "unstaged_files": unstaged, "files": files, "changed_symbols": symbols, "generated_files": generated, "diff": combined[:max_chars], "diff_truncated": len(combined) > max_chars}
