"""Dependency-free local relevance search using TF-IDF-style token scoring."""
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
_MAX_FILES = 1_000
_MAX_SIZE = 512 * 1024
_TOKEN = re.compile(r"[a-zA-Z0-9_]{2,}")


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text)]


def run(params: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    query = str(params.get("query") or "").strip()
    if not root.is_dir():
        return {"result": None, "error": f"Directory not found: {root}"}
    if not query:
        return {"result": None, "error": "'query' is required"}
    extensions = {str(value).lower() for value in params.get("file_extensions", [])}
    documents: list[tuple[Path, str, Counter[str]]] = []
    document_frequency: Counter[str] = Counter()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _SKIP for part in relative.parts) or not path.is_file():
            continue
        try:
            if path.stat().st_size > _MAX_SIZE or (extensions and path.suffix.lower() not in extensions):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        counts = Counter(_tokens(text))
        if counts:
            documents.append((path, text, counts))
            document_frequency.update(counts.keys())
        if len(documents) >= _MAX_FILES:
            break
    query_counts = Counter(_tokens(query))
    if not query_counts:
        return {"result": None, "error": "Query needs at least one word or identifier"}
    total = len(documents)
    scored = []
    for path, text, counts in documents:
        score = sum(query_count * (counts[token] / sum(counts.values())) * math.log((total + 1) / (document_frequency[token] + 1) + 1) for token, query_count in query_counts.items())
        if score <= 0:
            continue
        lines = text.splitlines()
        excerpt = next((line.strip() for line in lines if any(token in line.lower() for token in query_counts)), "")[:500]
        scored.append({"path": str(path), "score": round(score, 6), "excerpt": excerpt})
    max_results = max(1, min(int(params.get("max_results", 20)), 100))
    scored.sort(key=lambda item: (-item["score"], item["path"]))
    return {"result": {"matches": scored[:max_results], "match_count": len(scored[:max_results]),
            "files_scanned": total, "truncated": total >= _MAX_FILES, "method": "local_tfidf_token_ranking",
            "read_only": True}, "error": None}
