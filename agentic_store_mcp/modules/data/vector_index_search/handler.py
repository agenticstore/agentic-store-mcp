"""Opt-in, local-endpoint vector index creation and search."""
import json
import math
from pathlib import Path
from typing import Any

import httpx

_MAX_FILES = 500
_MAX_BYTES = 256 * 1024
_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


def _local_endpoint(url: str) -> bool:
    return url.startswith("http://127.0.0.1:") or url.startswith("http://localhost:")


def _embed(endpoint: str, model: str, texts: list[str]) -> list[list[float]]:
    response = httpx.post(endpoint, json={"model": model, "input": texts}, timeout=60.0)
    response.raise_for_status()
    data = response.json()
    vectors = data.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise ValueError("Embedding endpoint returned an unexpected response")
    return vectors


def _chunks(root: Path, extensions: set[str]) -> list[dict[str, str]]:
    chunks = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in _SKIP for part in relative.parts) or not path.is_file():
            continue
        try:
            if path.stat().st_size > _MAX_BYTES or (extensions and path.suffix.lower() not in extensions):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for offset in range(0, len(text), 2000):
            value = text[offset:offset + 2000].strip()
            if value:
                chunks.append({"path": str(path), "text": value})
            if len(chunks) >= _MAX_FILES:
                return chunks
    return chunks


def _score(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    magnitude = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / magnitude if magnitude else 0.0


def run(params: dict[str, Any]) -> dict[str, Any]:
    action = str(params.get("action") or "search")
    endpoint = str(params.get("endpoint") or "http://127.0.0.1:11434/api/embed")
    model = str(params.get("model") or "nomic-embed-text")
    index_path = Path(str(params.get("index_path") or "").strip()).expanduser().resolve()
    if action not in {"index", "search"}:
        return {"result": None, "error": "action must be 'index' or 'search'"}
    if not _local_endpoint(endpoint):
        return {"result": None, "error": "Only localhost embedding endpoints are allowed"}
    if not str(params.get("index_path") or "").strip():
        return {"result": None, "error": "'index_path' is required"}
    try:
        if action == "index":
            root = Path(str(params.get("path") or "").strip()).expanduser().resolve()
            if not root.is_dir():
                return {"result": None, "error": f"Directory not found: {root}"}
            if not params.get("confirm_write"):
                return {"result": None, "error": "Set confirm_write=true to save the local vector index"}
            extensions = {str(item).lower() for item in params.get("file_extensions", [])}
            chunks = _chunks(root, extensions)
            vectors = _embed(endpoint, model, [item["text"] for item in chunks])
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(json.dumps({"model": model, "chunks": [{**item, "vector": vector} for item, vector in zip(chunks, vectors)]}), encoding="utf-8")
            return {"result": {"index_path": str(index_path), "chunks_indexed": len(chunks), "endpoint": endpoint, "local_only": True}, "error": None}
        query = str(params.get("query") or "").strip()
        if not query:
            return {"result": None, "error": "'query' is required for search"}
        data = json.loads(index_path.read_text(encoding="utf-8"))
        query_vector = _embed(endpoint, str(data["model"]), [query])[0]
        results = [{"path": item["path"], "text": item["text"][:500], "score": round(_score(query_vector, item["vector"]), 6)} for item in data.get("chunks", [])]
        results.sort(key=lambda item: item["score"], reverse=True)
        limit = max(1, min(int(params.get("max_results", 10)), 100))
        return {"result": {"index_path": str(index_path), "matches": results[:limit], "match_count": len(results[:limit]), "local_only": True}, "error": None}
    except (OSError, ValueError, KeyError, json.JSONDecodeError, httpx.HTTPError) as exc:
        return {"result": None, "error": str(exc)}
