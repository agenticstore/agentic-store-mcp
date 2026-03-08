"""
AgenticStore MCP Tools
======================

Free, open-source MCP tools for AI agents.

Quickstart::

    from agentic_store_mcp import start_server

    start_server()                          # all tools
    start_server(modules=["code"])          # AgenticCode only
    start_server(tools=["agentic_web_search"])  # single tool
"""

from agentic_store_mcp.server import start_server

__all__ = ["start_server"]
