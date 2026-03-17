"""LLM-based prompt reviewer using local Ollama."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

OLLAMA_BASE = "http://localhost:11434"

PREDEFINED_SYSTEM_PROMPT = """You are a security and privacy firewall reviewing AI prompts before they reach external AI services.

Analyze the prompt for:
1. API keys, tokens, passwords, or credentials
2. PII: full names, emails, phone numbers, physical addresses, government IDs
3. Internal infrastructure: private IPs, internal hostnames, database connection strings
4. Sensitive file paths revealing system structure or usernames
5. Confidential business information: unreleased details, financial data

For each finding suggest a safe replacement (e.g. "[REDACTED_API_KEY]", "[REDACTED_EMAIL]").

Respond ONLY with valid JSON — no prose, no markdown fences:
{
  "safe": true,
  "findings": [
    {"type": "string", "original": "string", "replacement": "string"}
  ],
  "redacted_prompt": "full prompt with all findings replaced"
}

If the prompt is clean return: {"safe": true, "findings": [], "redacted_prompt": "<original>"}"""


async def review(prompt_text: str, model: str, custom_rules: list[str]) -> dict:
    """Send prompt to local Ollama model for security review."""
    system = PREDEFINED_SYSTEM_PROMPT
    if custom_rules:
        rules_block = "\n".join(f"- {r}" for r in custom_rules if r.strip())
        system += f"\n\nAdditional rules to enforce:\n{rules_block}"

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Review this prompt:\n\n{prompt_text}"},
                ],
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["message"]["content"]
        return json.loads(content)


async def list_models() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{OLLAMA_BASE}/api/tags")
        resp.raise_for_status()
        return resp.json().get("models", [])


async def pull_model(model_name: str) -> AsyncGenerator[dict, None]:
    async with httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE}/api/pull",
            json={"name": model_name, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    yield json.loads(line)


async def delete_model(model_name: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{OLLAMA_BASE}/api/delete", json={"name": model_name})
        resp.raise_for_status()


async def is_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
