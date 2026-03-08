# repo_scanner

> Scans a directory for leaked secrets, missing .gitignore entries, and PII exposure risks.

Runs three independent checks against any local directory. No API keys required. All scanning happens locally — nothing leaves your machine.

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | Yes | Directory to scan. Example: `"/Users/me/my-project"` |
| `checks` | `string` | No | Comma-separated checks to run. Default: `"all"`. Options: `secrets`, `gitignore`, `pii` |

## What Each Check Does

### `secrets`
Scans all text files for patterns matching known credential formats:
- AWS Access Key IDs and secret keys
- OpenAI, Anthropic, GitHub, Google, Slack API keys
- Private key blocks (RSA, EC, DSA, OPENSSH)
- Database connection URLs containing passwords
- Generic `api_key =`, `password =`, and bearer token patterns
- JWTs

**Findings include**: file path, line number, secret type, severity (`HIGH`/`MEDIUM`), and a redacted snippet showing only the first 6 characters.

Skips: binary files, files over 1 MB, `.git/`, `node_modules/`, `__pycache__/`, `.venv/`.

### `gitignore`
Checks whether sensitive files and directories exist locally but are not covered by `.gitignore`:
- `.env`, `.env.*` variants
- Private key files (`id_rsa`, `id_ed25519`, `*.pem`, `*.key`, `*.p12`)
- Credential files (`credentials.json`, `service-account.json`, `secrets.yml`)
- Build artifacts and dependency directories (`node_modules/`, `__pycache__/`, `.venv/`, `dist/`, `build/`)

Also flags if `.gitignore` itself is missing.

### `pii`
Scans data files (`.csv`, `.json`, `.yml`, `.yaml`, `.txt`, `.log`, `.sql`, `.xml`, `.md`) for personal information:
- Email addresses
- US Social Security Numbers
- Credit card numbers (4-block format)
- US phone numbers
- Private IP addresses

Reports the first occurrence per pattern per file, plus total count of occurrences.

## Required Setup

No API keys required. Works out of the box.

## Examples

### Example 1: Full scan of a project directory

Input:
```json
{
  "path": "/Users/me/my-project"
}
```

Output:
```json
{
  "path": "/Users/me/my-project",
  "summary": {
    "total_findings": 3,
    "secrets": 1,
    "gitignore_issues": 1,
    "pii": 1
  },
  "findings": {
    "secrets": [
      {
        "file": "config/settings.py",
        "line": 14,
        "type": "AWS Access Key ID",
        "severity": "HIGH",
        "snippet": "AKIAIO***[REDACTED]"
      }
    ],
    "gitignore_issues": [
      {
        "file": ".env",
        "issue": "Sensitive file exists and is not covered by .gitignore",
        "severity": "HIGH"
      }
    ],
    "pii": [
      {
        "file": "data/users.csv",
        "line": 2,
        "type": "Email Address",
        "severity": "MEDIUM",
        "occurrences_in_file": 47
      }
    ]
  }
}
```

### Example 2: Secrets check only

Input:
```json
{
  "path": "/Users/me/my-project",
  "checks": "secrets"
}
```

### Example 3: Gitignore + secrets only

Input:
```json
{
  "path": "/Users/me/my-project",
  "checks": "secrets,gitignore"
}
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Path does not exist` | Wrong path or typo | Use an absolute path. Check it exists with `ls` first |
| `Path is not a directory` | You passed a file path | Pass the parent directory, not a specific file |
| `Unknown checks: {'malware'}` | Invalid check name | Only `secrets`, `gitignore`, `pii` are valid |
| Empty `findings` when you expect results | File type not scanned | PII check only scans data files (`.csv`, `.json`, etc.). Secrets check skips binary files and files over 1 MB |

## Notes

- Secrets are always redacted in output — only the first 6 characters are shown.
- The scanner uses regex patterns and will produce false positives (e.g. example keys in documentation). Review findings manually.
- PII scanning is intentionally limited to data file types to reduce noise. Source code files are not scanned for PII.
- Files already in `.gitignore` may still be flagged by the `secrets` check — being gitignored reduces risk but does not eliminate the credential from your local history.
