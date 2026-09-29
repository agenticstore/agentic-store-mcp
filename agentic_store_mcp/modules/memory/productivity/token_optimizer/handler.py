"""
token_optimizer — compress code or text to reduce token count.

Strategies:
  compress  — strip comments, docstrings, blank lines, excess whitespace
  summarize — produce a structural outline (functions/classes/logic)
  both      — compress then append summary
"""
from __future__ import annotations

import re


# ─── Language detection ───────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """Best-effort language detection from content signals."""
    sample = text[:2000]
    if re.search(r"^\s*def |^\s*class |^\s*import |^\s*from .+ import", sample, re.M):
        return "python"
    if re.search(r"^\s*(function|const|let|var|=>|require\(|import .+ from)", sample, re.M):
        return "javascript"
    if re.search(r"^\s*func |^package |^import \(", sample, re.M):
        return "go"
    if re.search(r"^\s*fn |^use |^pub (fn|struct|enum|impl)", sample, re.M):
        return "rust"
    if re.search(r"^\s*(public|private|protected|class|interface|void|int|String)\s", sample, re.M):
        return "java"
    if re.search(r"^\s*(#include|int main|std::)", sample, re.M):
        return "cpp"
    if re.search(r"^#!/.*(bash|sh|zsh)", sample, re.M) or re.search(r"^\s*(echo|export|if \[)", sample, re.M):
        return "shell"
    return "unknown"


# ─── Comment stripping ────────────────────────────────────────────────────────

def _strip_python(text: str) -> str:
    # Remove triple-quoted docstrings (both ''' and """)
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    text = re.sub(r"'''[\s\S]*?'''", "", text)
    # Remove inline # comments (but not shebang on line 1)
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if i == 0 and line.startswith("#!"):
            out.append(line)
            continue
        stripped = re.sub(r"\s*#.*$", "", line)
        out.append(stripped)
    return "\n".join(out)


def _strip_c_style(text: str) -> str:
    # Remove /* ... */ block comments
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    # Remove // line comments
    lines = [re.sub(r"\s*//.*$", "", line) for line in text.splitlines()]
    return "\n".join(lines)


def _strip_shell(text: str) -> str:
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if i == 0 and line.startswith("#!"):
            out.append(line)
            continue
        stripped = re.sub(r"\s*#.*$", "", line)
        out.append(stripped)
    return "\n".join(out)


_STRIP_FN = {
    "python": _strip_python,
    "javascript": _strip_c_style,
    "typescript": _strip_c_style,
    "go": _strip_c_style,
    "rust": _strip_c_style,
    "java": _strip_c_style,
    "c": _strip_c_style,
    "cpp": _strip_c_style,
    "shell": _strip_shell,
}


def _compress(text: str, language: str, preserve_structure: bool) -> str:
    strip_fn = _STRIP_FN.get(language)
    if strip_fn:
        text = strip_fn(text)

    lines = text.splitlines()
    # Drop lines that are now purely whitespace
    lines = [ln for ln in lines if ln.strip()]

    if preserve_structure:
        # Re-insert a single blank line before top-level definitions
        result: list[str] = []
        _def_re = re.compile(r"^(def |class |func |fn |function |public |private |protected )")
        for line in lines:
            if _def_re.match(line.lstrip()) and result:
                result.append("")
            result.append(line)
        lines = result

    return "\n".join(lines)


# ─── Summarizer ───────────────────────────────────────────────────────────────

def _summarize(text: str, language: str) -> str:
    """Extract a structural outline: top-level defs, classes, key imports."""
    lines = text.splitlines()
    outline: list[str] = []

    if language == "python":
        for line in lines:
            s = line.strip()
            if s.startswith(("def ", "class ", "async def ")):
                # Keep only the signature line (up to the colon)
                sig = s.split(":")[0] + ":"
                indent = len(line) - len(line.lstrip())
                outline.append(" " * indent + sig)
            elif s.startswith(("import ", "from ")) and len(outline) < 20:
                outline.append(s)
    elif language in ("javascript", "typescript"):
        for line in lines:
            s = line.strip()
            if re.match(r"(export\s+)?(async\s+)?function\s+\w+|const\s+\w+\s*=\s*(async\s*)?\(|class\s+\w+", s):
                outline.append(s.split("{")[0].strip())
    elif language == "go":
        for line in lines:
            s = line.strip()
            if re.match(r"func\s+|type\s+\w+\s+(struct|interface)", s):
                outline.append(s.split("{")[0].strip())
    else:
        # Generic: lines that look like definitions (short, end with { or :)
        for line in lines:
            s = line.strip()
            if len(s) < 120 and (s.endswith((":")) or re.match(r"\w[\w\s<>*&]*([(:{])", s)):
                outline.append(s)
            if len(outline) >= 40:
                break

    if not outline:
        # Fallback: first non-blank line + line count
        first = next((ln.strip() for ln in lines if ln.strip()), "")
        return f"[{language}] {len(lines)} lines. Starts with: {first[:120]}"

    return f"[{language} outline — {len(lines)} lines]\n" + "\n".join(outline[:60])


# ─── Token estimation ─────────────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """Rough GPT-style token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


# ─── Entry point ─────────────────────────────────────────────────────────────

def run(params: dict) -> dict:
    text = params.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return {"result": None, "error": "'text' is required and must be a non-empty string"}

    mode = params.get("mode", "compress")
    if mode not in ("compress", "summarize", "both"):
        return {"result": None, "error": f"Invalid mode '{mode}'. Choose: compress, summarize, both"}

    language = (params.get("language") or "auto").strip().lower()
    if language == "auto":
        language = _detect_language(text)

    preserve_structure = bool(params.get("preserve_structure", True))

    original_tokens = _estimate_tokens(text)
    output_parts: list[str] = []

    try:
        if mode in ("compress", "both"):
            compressed = _compress(text, language, preserve_structure)
            output_parts.append(compressed)

        if mode in ("summarize", "both"):
            src = compressed if mode == "both" else text
            summary = _summarize(src, language)
            if mode == "both":
                output_parts.append("\n\n# --- SUMMARY ---\n" + summary)
            else:
                output_parts = [summary]

        output = "\n".join(output_parts)
        output_tokens = _estimate_tokens(output)
        saved = original_tokens - output_tokens
        ratio = round((saved / original_tokens) * 100, 1) if original_tokens else 0

        return {
            "result": {
                "output": output,
                "language_detected": language,
                "mode": mode,
                "original_tokens_est": original_tokens,
                "output_tokens_est": output_tokens,
                "tokens_saved_est": saved,
                "compression_pct": ratio,
            },
            "error": None,
        }
    except Exception as e:
        return {"result": None, "error": str(e)}
