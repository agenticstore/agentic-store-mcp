"""Visit prompt text without modifying model IDs or binary/image data."""

from __future__ import annotations

import json
from typing import Callable

_TEXT_KEYS = {
    "system",
    "instructions",
    "input",
    "content",
    "text",
    "output",
    "prompt",
    "description",
}
_ROOT_KEYS = {
    "response",
    "system",
    "instructions",
    "input",
    "messages",
    "contents",
    "tools",
    "prompt",
}


def map_prompt(body: dict, transform: Callable[[str], str]) -> dict:
    """Copy a request, transforming text and structured tool argument leaves."""

    def walk(value, key="", all_strings=False):
        if isinstance(value, dict):
            return {
                k: walk(
                    v,
                    k,
                    all_strings or (k == "input" and value.get("type") == "tool_use"),
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [walk(v, key, all_strings) for v in value]
        if isinstance(value, str):
            if key == "arguments":
                try:
                    parsed = json.loads(value)
                except ValueError:
                    return transform(value)
                return json.dumps(walk(parsed, all_strings=True), ensure_ascii=False)
            if all_strings or key in _TEXT_KEYS:
                return transform(value)
        return value

    return {k: walk(v, k) if k in _ROOT_KEYS else v for k, v in body.items()}


def extract_prompt(body: dict) -> str:
    parts = []

    def collect(text):
        parts.append(text)
        return text

    map_prompt(body, collect)
    return "\n".join(parts)
