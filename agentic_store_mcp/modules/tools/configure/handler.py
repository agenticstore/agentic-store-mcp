"""
configure — set, get, remove, or list API tokens for any service connector.

Uses the AgenticStore secrets layer (keyring → config file fallback).
Service name convention: "{connector_slug}_{field_name}"
  e.g. "github_token", "openai_api_key", "anthropic_api_key"
"""
from __future__ import annotations

from typing import Any

from agentic_store_mcp.secrets import get_token, set_token, remove_token, list_tokens


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for configure.

    Actions:
        set    — store a token for a service (requires: service, token)
        get    — retrieve a token value (requires: service)
        remove — delete a stored token (requires: service)
        list   — list all service names with stored tokens (no values)
    """
    action = params.get("action", "").strip().lower()
    service = (params.get("service") or "").strip()
    token = (params.get("token") or "").strip()

    if action not in ("set", "get", "remove", "list"):
        return {
            "result": None,
            "error": f"Unknown action '{action}'. Valid actions: set, get, remove, list",
        }

    if action == "list":
        names = list_tokens()
        return {
            "result": {
                "action": "list",
                "services": names,
                "count": len(names),
                "note": "Only services stored in the config file are listed. Keyring-only entries are not enumerable.",
            },
            "error": None,
        }

    if not service:
        return {
            "result": None,
            "error": f"'service' is required for action '{action}'. Example: 'github_token'",
        }

    if action == "set":
        if not token:
            return {
                "result": None,
                "error": "'token' value is required for action 'set'",
            }
        set_token(service, token)
        return {
            "result": {
                "action": "set",
                "service": service,
                "status": "saved",
                "note": "Token stored securely. It will be used automatically by tools that require this connector.",
            },
            "error": None,
        }

    if action == "get":
        value = get_token(service)
        if value is None:
            return {
                "result": {
                    "action": "get",
                    "service": service,
                    "found": False,
                    "value": None,
                },
                "error": None,
            }
        return {
            "result": {
                "action": "get",
                "service": service,
                "found": True,
                "value": value,
            },
            "error": None,
        }

    if action == "remove":
        remove_token(service)
        return {
            "result": {
                "action": "remove",
                "service": service,
                "status": "removed",
            },
            "error": None,
        }

    return {"result": None, "error": f"Unhandled action: {action}"}
