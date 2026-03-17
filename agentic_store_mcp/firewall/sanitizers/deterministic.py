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
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_OPENAI_KEY]"),
    (r"sk-ant-[a-zA-Z0-9\-_]{20,}", "[REDACTED_ANTHROPIC_KEY]"),
    (r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    (r"ghs_[a-zA-Z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
    (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
    (r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", "[REDACTED_JWT]"),
    (r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", "[REDACTED_BEARER_TOKEN]"),
    (r"(?i)(?:password|passwd|secret|api[_\-]?key|token)\s*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?", "[REDACTED_SECRET]"),
]

_HIGH_ENTROPY_PATTERN = re.compile(r"[a-zA-Z0-9/+]{32,}={0,2}")

_PII_PATTERNS: list[tuple[str, str]] = [
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "[REDACTED_EMAIL]"),
    (r"\b(?:\+1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b", "[REDACTED_PHONE]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
    (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b", "[REDACTED_CARD]"),
]

_FILE_PATH_PATTERNS: list[tuple[str, str]] = [
    (r"/(?:home|Users|root)/[a-zA-Z0-9_.\-]+(?:/[^\s,;\"']+)*", "[REDACTED_PATH]"),
    (r"[A-Z]:\\(?:Users|Documents|Program Files)[^\s,;\"']*", "[REDACTED_PATH]"),
]

_IP_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b", "[REDACTED_INTERNAL_IP]"),
]


def _shannon_entropy(s: str) -> float:
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((count / n) * math.log2(count / n) for count in freq.values())


def sanitize(text: str, config: dict) -> tuple[str, list[Finding]]:
    """Apply deterministic sanitization rules. Returns (redacted_text, findings)."""
    findings: list[Finding] = []
    det = config.get("deterministic", {})

    if det.get("secrets", True):
        for pattern, replacement in _SECRET_PATTERNS:
            for match in re.finditer(pattern, text):
                rep = replacement or "[REDACTED_SECRET]"
                findings.append(Finding("secret", match.group(), rep))
            text = re.sub(pattern, replacement or "[REDACTED_SECRET]", text)

        for match in _HIGH_ENTROPY_PATTERN.finditer(text):
            val = match.group()
            if _shannon_entropy(val) > 4.5 and not val.startswith("[REDACTED"):
                findings.append(Finding("high_entropy_secret", val, "[REDACTED_HIGH_ENTROPY]"))
                text = text.replace(val, "[REDACTED_HIGH_ENTROPY]", 1)

    if det.get("pii", True):
        for pattern, replacement in _PII_PATTERNS:
            for match in re.finditer(pattern, text):
                findings.append(Finding("pii", match.group(), replacement))
            text = re.sub(pattern, replacement, text)

    if det.get("file_paths", True):
        for pattern, replacement in _FILE_PATH_PATTERNS:
            for match in re.finditer(pattern, text):
                findings.append(Finding("file_path", match.group(), replacement))
            text = re.sub(pattern, replacement, text)

    if det.get("ip_addresses", True):
        for pattern, replacement in _IP_PATTERNS:
            for match in re.finditer(pattern, text):
                findings.append(Finding("ip_address", match.group(), replacement))
            text = re.sub(pattern, replacement, text)

    return text, findings
