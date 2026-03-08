#!/usr/bin/env python3
"""
Thin entry point for clone-and-run mode: uv run server.py

All logic lives in agentic_store_mcp/server.py so it works
identically whether run locally or installed via PyPI / uvx.
"""
from agentic_store_mcp.server import main

if __name__ == "__main__":
    main()
