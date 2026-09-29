"""Deterministic sanitizer — regex + entropy based."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass
class Finding:
    type: str
    original: str
    replacement: str


_SECRET_PATTERNS: list[tuple[str, str | None]] = [
    (r"sk-ant-[a-zA-Z0-9\-_]{20,}", "[REDACTED_ANTHROPIC_KEY]"),
    (r"sk-(?:proj-|svcacct-)?[a-zA-Z0-9_\-]{20,}", "[REDACTED_OPENAI_KEY]"),
    (r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    (r"ghs_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
    (r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", "[REDACTED_JWT]"),
    (r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", "[REDACTED_BEARER_TOKEN]"),
    (
        r"(?i)(?:password|passwd|secret|api[_\-]?key|token)\s*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?",
        "[REDACTED_SECRET]",
    ),
]

_HIGH_ENTROPY_PATTERN = re.compile(r"[a-zA-Z0-9/+]{32,}={0,2}")

_PII_PATTERNS: list[tuple[str, str]] = [
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "[REDACTED_EMAIL]"),
    (r"\b(?:\+1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b", "[REDACTED_PHONE]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
    (
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
        "[REDACTED_CARD]",
    ),
]

_FILE_PATH_PATTERNS: list[tuple[str, str]] = [
    (r"/(?:home|Users|root)/[a-zA-Z0-9_.\-]+(?:/[^\s,;\"']+)*", "[REDACTED_PATH]"),
    (r"[A-Z]:\\(?:Users|Documents|Program Files)[^\s,;\"']*", "[REDACTED_PATH]"),
]

_IP_PATTERNS: list[tuple[str, str]] = [
    (
        r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b",
        "[REDACTED_INTERNAL_IP]",
    ),
]


def _shannon_entropy(s: str) -> float:
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((count / n) * math.log2(count / n) for count in freq.values())


def sanitize(text: str, config: dict) -> tuple[str, list[Finding]]:
    """Apply deterministic sanitization rules. Returns (redacted_text, findings)."""
    det = config.get("deterministic", {})
    custom = config.get("redaction_text")
    spans: list[tuple[int, int, Finding]] = []

    def add(start, end, kind, default):
        if any(start < e and end > b for b, e, _ in spans):
            return
        replacement = custom if isinstance(custom, str) and custom else default
        spans.append((start, end, Finding(kind, text[start:end], replacement)))

    groups = [
        ("secrets", "secret", _SECRET_PATTERNS),
        ("pii", "pii", _PII_PATTERNS),
        ("file_paths", "file_path", _FILE_PATH_PATTERNS),
        ("ip_addresses", "ip_address", _IP_PATTERNS),
    ]
    for setting, kind, patterns in groups:
        if det.get(setting, True):
            for pattern, default in patterns:
                for match in re.finditer(pattern, text):
                    add(
                        match.start(), match.end(), kind, default or "[REDACTED_SECRET]"
                    )
    if det.get("secrets", True):
        for match in _HIGH_ENTROPY_PATTERN.finditer(text):
            if _shannon_entropy(match.group()) > 4.5:
                add(
                    match.start(),
                    match.end(),
                    "high_entropy_secret",
                    "[REDACTED_HIGH_ENTROPY]",
                )
    spans.sort(key=lambda span: span[0])
    parts = []
    offset = 0
    for start, end, finding in spans:
        parts.extend((text[offset:start], finding.replacement))
        offset = end
    parts.append(text[offset:])
    return "".join(parts), [finding for _, _, finding in spans]
