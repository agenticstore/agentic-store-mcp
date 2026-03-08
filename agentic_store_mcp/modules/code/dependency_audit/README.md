# dependency_audit

> Scans requirements.txt, pyproject.toml, Pipfile, and package.json for outdated and vulnerable dependencies.

Checks every dependency against the PyPI and npm registries for the latest version, and queries the [OSV database](https://osv.dev) for known security vulnerabilities. Runs all checks concurrently — a project with 50 dependencies typically finishes in under 10 seconds.

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | Yes | Directory to scan. Example: `"/Users/me/my-project"` |

## Required Setup

No API keys required. Uses only free, public APIs:
- [PyPI JSON API](https://pypi.org/pypi/{package}/json)
- [npm registry](https://registry.npmjs.org/{package}/latest)
- [OSV API](https://api.osv.dev) — Open Source Vulnerabilities database

## What it scans

| File | Language / Ecosystem | Version check | Vulnerability check |
|------|----------------------|--------------|---------------------|
| `requirements.txt` | Python | PyPI API | OSV |
| `pyproject.toml` | Python (PEP 621 + Poetry) | PyPI API | OSV |
| `Pipfile` | Python | PyPI API | OSV |
| `package.json` | JavaScript, TypeScript, React, Next.js, Vue, Svelte — anything npm | npm registry | OSV |
| `go.mod` | Go | Go module proxy | OSV |
| `pom.xml` | Java (Maven) | Maven Central | OSV |
| `build.gradle` / `build.gradle.kts` | Java (Gradle) | Maven Central | OSV |
| `conanfile.txt` / `conanfile.py` | C++ (Conan) | not available | OSV (ConanCenter) |
| `vcpkg.json` | C++ (vcpkg) | not available | not available |

All files present in the directory are scanned. Results are deduplicated when the same package appears in multiple files.

**React / Next.js / TypeScript**: these all use `package.json` — no extra setup needed.

## Examples

### Example 1: Full audit

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
  "files_scanned": ["requirements.txt", "package.json"],
  "summary": {
    "total": 12,
    "vulnerable": 1,
    "outdated": 3,
    "up_to_date": 8
  },
  "findings": {
    "python": [
      {
        "package": "requests",
        "current_version": "2.28.0",
        "latest_version": "2.31.0",
        "outdated": true,
        "vulnerable": true,
        "vulnerabilities": [
          {
            "id": "GHSA-j8r2-6x86-q33q",
            "summary": "Unintended leak of proxy-authorization header",
            "severity": "MEDIUM",
            "url": "https://osv.dev/vulnerability/GHSA-j8r2-6x86-q33q"
          }
        ]
      },
      {
        "package": "fastapi",
        "current_version": "0.100.0",
        "latest_version": "0.111.0",
        "outdated": true,
        "vulnerable": false,
        "vulnerabilities": []
      }
    ],
    "npm": []
  }
}
```

Results are sorted: vulnerable packages first, then outdated, then alphabetical.

### Example 2: Clean project

```json
{
  "summary": {
    "total": 8,
    "vulnerable": 0,
    "outdated": 0,
    "up_to_date": 8
  }
}
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `No dependency files found` | Directory has no supported dependency files | Check you're pointing at the project root, not a subdirectory |
| `parse_errors` field present in result | One file failed to parse | Check the named file for syntax errors (e.g. invalid TOML) |
| `latest_version: "unknown"` | Package not found on PyPI/npm | Private or renamed package — version comparison is skipped |
| `current_version: "unpinned"` | Dependency uses `>=` or `~=` instead of `==` | Exact version unknown; vulnerability check still runs, outdated check skipped |
| Slow on large projects | Many dependencies, sequential network calls | Tool uses concurrent requests (up to 10 at once); normal for 50+ deps |

## Notes

- Only `==` pins are treated as the current version. Packages using `>=`, `~=`, or `^` show `"unpinned"` and are not compared against the latest version.
- Vulnerability results are capped at 5 per package. Follow the `url` field to see the full advisory.
- `up_to_date` counts packages that are neither outdated nor vulnerable. A package can be both outdated and vulnerable — it is not double-counted.
- Dev dependencies in `package.json` (`devDependencies`) are included in the audit.
