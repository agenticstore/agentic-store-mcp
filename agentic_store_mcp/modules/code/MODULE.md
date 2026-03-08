# AgenticCode

> Tools for code security, quality, and repository hygiene.

## Tools

| Tool | Description | Required API Keys |
|------|-------------|-------------------|
| [`repo_scanner`](repo_scanner/README.md) | Scan a directory for leaked secrets, missing .gitignore entries, and PII exposure | None |
| [`dependency_audit`](dependency_audit/README.md) | Check dependencies for outdated versions and known vulnerabilities | None |
| [`python_lint_checker`](python_lint_checker/README.md) | Static analysis for Python — unused imports, bugs, style, complexity | None |

## Required API Keys

No API keys required for current tools in this module.

## Quick Setup

```bash
python setup_cli.py --modules code --client claude-desktop
```

Or manually — add to your client config:

```json
{
  "mcpServers": {
    "agentic-store-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/agentic-store-mcp",
               "server.py", "--modules", "code"],
      "env": {}
    }
  }
}
```
