"""
analyze_commits — local git commit history analysis.

Pure subprocess + stdlib. No network access, no API key required.
"""
from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def _git(args: list[str], cwd: str) -> tuple[str, str]:
    """Run a git command, return (stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout, result.stderr


def _is_git_repo(path: str) -> bool:
    _, err = _git(["rev-parse", "--git-dir"], cwd=path)
    return not err.strip()


def _parse_commits(path: str, since: str | None, until: str | None, author: str | None, max_commits: int) -> list[dict]:
    """Parse git log into structured commit dicts."""
    SEP = "||SEP||"
    fmt = f"%H{SEP}%an{SEP}%ae{SEP}%ai{SEP}%s"

    args = ["log", f"--format={fmt}", f"-n{max_commits}"]
    if since:
        args += [f"--since={since}"]
    if until:
        args += [f"--until={until}"]
    if author:
        args += [f"--author={author}"]

    stdout, stderr = _git(args, cwd=path)
    if stderr.strip() and not stdout.strip():
        return []

    commits = []
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split(SEP)
        if len(parts) < 5:
            continue
        sha, name, email, date, subject = parts[0], parts[1], parts[2], parts[3], SEP.join(parts[4:])
        commits.append({
            "sha": sha[:12],
            "author_name": name,
            "author_email": email,
            "date": date.strip(),
            "message": subject.strip(),
        })
    return commits


def _file_stats(path: str, sha: str) -> dict:
    """Get files changed in a specific commit."""
    stdout, _ = _git(["show", "--stat", "--format=", sha], cwd=path)
    changed, insertions, deletions = 0, 0, 0
    files = []
    for line in stdout.strip().splitlines():
        if "|" in line:
            fname = line.split("|")[0].strip()
            files.append(fname)
            changed += 1
        elif "insertion" in line or "deletion" in line:
            import re
            ins = re.search(r"(\d+) insertion", line)
            dels = re.search(r"(\d+) deletion", line)
            if ins:
                insertions += int(ins.group(1))
            if dels:
                deletions += int(dels.group(1))
    return {"files_changed": changed, "insertions": insertions, "deletions": deletions, "files": files[:10]}


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for analyze_commits.

    Params:
        path         Path to local git repository (required)
        since        Filter: commits after this date (optional)
        until        Filter: commits before this date (optional)
        author       Filter: by author name/email (optional)
        max_commits  Max commits to return (default: 50)
    """
    path_str = params.get("path", "")
    if not path_str:
        return {"result": None, "error": "'path' is required"}

    root = Path(path_str).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return {"result": None, "error": f"Path does not exist or is not a directory: {path_str}"}

    if not _is_git_repo(str(root)):
        return {"result": None, "error": f"Not a git repository: {path_str}"}

    since = params.get("since") or None
    until = params.get("until") or None
    author = params.get("author") or None
    max_commits = int(params.get("max_commits") or 50)

    commits = _parse_commits(str(root), since, until, author, max_commits)

    if not commits:
        return {
            "result": {
                "path": str(root),
                "total_commits": 0,
                "commits": [],
                "summary": {"authors": {}, "busiest_days": []},
            },
            "error": None,
        }

    # Summary stats
    author_counts: Counter = Counter(c["author_name"] for c in commits)
    day_counts: Counter = Counter(c["date"][:10] for c in commits)

    result: dict[str, Any] = {
        "path": str(root),
        "total_commits": len(commits),
        "filters": {k: v for k, v in {"since": since, "until": until, "author": author}.items() if v},
        "commits": commits,
        "summary": {
            "authors": dict(author_counts.most_common(10)),
            "busiest_days": [{"date": d, "commits": n} for d, n in day_counts.most_common(5)],
            "date_range": {
                "earliest": commits[-1]["date"][:10] if commits else None,
                "latest": commits[0]["date"][:10] if commits else None,
            },
        },
    }

    return {"result": result, "error": None}
