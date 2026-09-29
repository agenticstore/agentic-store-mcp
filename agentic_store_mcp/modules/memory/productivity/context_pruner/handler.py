"""
context_pruner — recommend which context items an agent can safely drop.

Scores each item by keyword overlap with the task description.
No file reads, no network — purely local text analysis.
"""
from __future__ import annotations

import re
from collections import Counter


# ─── Text utilities ───────────────────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "in", "of", "to", "and", "or", "for",
    "it", "be", "as", "at", "by", "we", "he", "she", "this", "that",
    "with", "from", "on", "are", "was", "has", "have", "not", "but",
    "if", "do", "so", "my", "our", "get", "use", "can", "will", "how",
    "what", "when", "which", "your", "its", "into", "than", "then",
    "them", "they", "all", "been", "would", "could", "should",
})


def _tokenize(text: str) -> list[str]:
    """Lowercase words + path segments, filtered for stop words."""
    # Split on non-alphanumeric, also split camelCase and snake_case
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)  # camelCase
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9]{1,}", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _item_tokens(item: str) -> list[str]:
    """Extract tokens from a file path or tool name."""
    # File paths: use filename + parent dir name as the most relevant signals
    parts = re.split(r"[/\\]", item)
    relevant_parts = parts[-3:]  # last 3 path segments
    combined = " ".join(relevant_parts)
    # Also expand the full item
    return _tokenize(combined) + _tokenize(item)


def _score(task_tokens: Counter, item: str) -> tuple[float, list[str]]:
    """Return (relevance_score, matched_keywords)."""
    item_toks = set(_item_tokens(item))
    matches = [t for t in item_toks if t in task_tokens]
    if not matches:
        return 0.0, []
    # Weight by task token frequency so rare/specific terms score higher
    score = sum(task_tokens[m] for m in matches) / max(len(task_tokens), 1)
    return round(score, 4), sorted(set(matches))


# ─── Entry point ─────────────────────────────────────────────────────────────

def run(params: dict) -> dict:
    task = (params.get("task") or "").strip()
    if not task:
        return {"result": None, "error": "'task' is required"}

    items = params.get("items")
    if not items or not isinstance(items, list):
        return {"result": None, "error": "'items' must be a non-empty list of strings"}

    items = [str(i) for i in items if str(i).strip()]
    if not items:
        return {"result": None, "error": "'items' list contains no valid entries"}

    keep_top_n = max(1, int(params.get("keep_top_n", 5)))
    verbose = bool(params.get("verbose", False))

    try:
        task_tokens: Counter = Counter(_tokenize(task))

        scored = []
        for item in items:
            score, matches = _score(task_tokens, item)
            scored.append({"item": item, "score": score, "matches": matches})

        scored.sort(key=lambda x: x["score"], reverse=True)

        keep = scored[:keep_top_n]
        drop = scored[keep_top_n:]

        # Items with zero score are "safe to drop" regardless of keep_top_n
        zero_score_in_keep = [s for s in keep if s["score"] == 0.0]
        if zero_score_in_keep:
            # Promote them to the drop list — they have no relevance signal at all
            drop = zero_score_in_keep + drop
            keep = [s for s in keep if s["score"] > 0.0]

        def _fmt(entries: list[dict], include_scores: bool) -> list:
            if include_scores:
                return [
                    {"item": e["item"], "score": e["score"], "matched_keywords": e["matches"]}
                    for e in entries
                ]
            return [e["item"] for e in entries]

        result: dict = {
            "keep": _fmt(keep, verbose),
            "drop": _fmt(drop, verbose),
            "keep_count": len(keep),
            "drop_count": len(drop),
            "task_keywords": list(task_tokens.keys())[:20],
        }

        if drop:
            result["rationale"] = (
                f"Items in 'drop' share no keyword overlap with the task. "
                f"Removing them saves context without affecting the task: \"{task[:80]}\"."
            )
        else:
            result["rationale"] = "All items appear relevant to the current task — nothing safe to drop."

        return {"result": result, "error": None}

    except Exception as e:
        return {"result": None, "error": str(e)}
