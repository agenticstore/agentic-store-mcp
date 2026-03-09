"""
dependency_audit — scan a project for outdated and vulnerable dependencies.

Supported ecosystems:
  Python     — requirements.txt, pyproject.toml (PEP 621 + Poetry), Pipfile
  JavaScript — package.json  (covers JavaScript, TypeScript, React, Next.js, Vue, etc.)
  Go         — go.mod
  Java       — pom.xml (Maven), build.gradle / build.gradle.kts (Gradle)
  C++        — conanfile.txt, conanfile.py (Conan), vcpkg.json (vcpkg)

Version registry APIs (all free, no keys):
  PyPI    → pypi.org/pypi/{pkg}/json
  npm     → registry.npmjs.org/{pkg}/latest
  Go      → proxy.golang.org/{module}/@latest
  Maven   → search.maven.org (used for both Maven and Gradle)
  Conan   → no clean public API — vulnerability check only via OSV
  vcpkg   → no public API — dependency listing only (no version/vuln check)

Vulnerability data: osv.dev (OSV) — free, no key, covers all ecosystems above except vcpkg.
"""
import json
import re
import tomllib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MAX_WORKERS = 10
REQUEST_TIMEOUT = 10

# Maps internal ecosystem name → OSV ecosystem string (None = not supported)
OSV_ECOSYSTEM: dict[str, str | None] = {
    "PyPI": "PyPI",
    "npm": "npm",
    "Go": "Go",
    "Maven": "Maven",
    "ConanCenter": "ConanCenter",
    "vcpkg": None,
}

# Maps internal ecosystem name → output group key
ECOSYSTEM_GROUP: dict[str, str] = {
    "PyPI": "python",
    "npm": "javascript",
    "Go": "go",
    "Maven": "java",
    "ConanCenter": "cpp",
    "vcpkg": "cpp",
}


# ─── HTTP helper ──────────────────────────────────────────────────────────────


def _http(url: str, method: str = "GET", body: bytes | None = None) -> dict | None:
    """Make an HTTP request and return the parsed JSON response, or None on any error."""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "agentic-store-mcp/1.0",
        "Accept": "application/json",
    }
    try:
        req = Request(url, data=body, method=method, headers=headers)
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError, TimeoutError, OSError):
        return None


# ─── Python parsers ───────────────────────────────────────────────────────────


def _py_name_version(spec: str) -> tuple[str, str | None]:
    """Parse a PEP 508 dep spec → (normalised-name, pinned-version-or-None)."""
    spec = re.sub(r"\[.*?\]", "", spec).split(";")[0].strip()
    m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([=<>!~^]+)\s*([\w\.\*]+)?", spec)
    if not m:
        return spec.strip(), None
    name = re.sub(r"[-_.]+", "-", m.group(1)).lower()
    version = m.group(3) if m.group(2) in ("==", "===") else None
    return name, version


def parse_requirements_txt(path: Path) -> list[dict]:
    """Parse a requirements.txt file and return a list of package dicts."""
    packages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-", "git+", "http://", "https://", "file://")):
            continue
        name, version = _py_name_version(line)
        if name:
            packages.append({"name": name, "current_version": version, "ecosystem": "PyPI"})
    return packages


def parse_pyproject_toml(path: Path) -> list[dict]:
    """Parse PEP 621 [project.dependencies] and Poetry [tool.poetry.dependencies] from pyproject.toml."""
    packages = []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for dep in data.get("project", {}).get("dependencies", []):
        name, version = _py_name_version(dep)
        if name:
            packages.append({"name": name, "current_version": version, "ecosystem": "PyPI"})
    for name, spec in data.get("tool", {}).get("poetry", {}).get("dependencies", {}).items():
        if name.lower() == "python":
            continue
        raw = spec if isinstance(spec, str) else (spec.get("version", "") if isinstance(spec, dict) else "")
        m = re.search(r"\d+\.\d+[\.\d]*", raw)
        packages.append(
            {
                "name": re.sub(r"[-_.]+", "-", name).lower(),
                "current_version": m.group() if m else None,
                "ecosystem": "PyPI",
            }
        )
    return packages


def parse_pipfile(path: Path) -> list[dict]:
    """Parse packages and dev-packages from a Pipfile (TOML format)."""
    packages = []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for section in ("packages", "dev-packages"):
        for name, spec in data.get(section, {}).items():
            version = None
            if isinstance(spec, str) and spec != "*":
                m = re.search(r"\d+\.\d+[\.\d]*", spec)
                version = m.group() if m else None
            packages.append(
                {
                    "name": re.sub(r"[-_.]+", "-", name).lower(),
                    "current_version": version,
                    "ecosystem": "PyPI",
                }
            )
    return packages


# ─── JavaScript / npm parser ──────────────────────────────────────────────────
# Covers: JavaScript, TypeScript, React, Next.js, Vue, Svelte — anything using package.json.


def parse_package_json(path: Path) -> list[dict]:
    """Parse dependencies and devDependencies from a package.json file."""
    packages = []
    data = json.loads(path.read_text(encoding="utf-8"))
    for section in ("dependencies", "devDependencies"):
        for name, spec in data.get(section, {}).items():
            if not isinstance(spec, str) or spec.startswith(("file:", "git+", "github:", "http")):
                continue
            clean = re.sub(r"^[^\d]*", "", spec).strip()
            version = clean if re.match(r"^\d+\.\d+", clean) else None
            packages.append({"name": name, "current_version": version, "ecosystem": "npm"})
    return packages


# ─── Go parser ────────────────────────────────────────────────────────────────


def parse_go_mod(path: Path) -> list[dict]:
    """
    Parse go.mod require directives.
    Skips the module's own path declaration and indirect-only deps are included
    (they are still resolved and could be vulnerable).
    """
    packages = []
    content = path.read_text(encoding="utf-8")
    # Match both single-line: require github.com/foo/bar v1.2.3
    # and block-style:
    #   require (
    #       github.com/foo/bar v1.2.3
    #   )
    seen: set[str] = set()

    def _add(name: str, version: str) -> None:
        if name not in ("go", "require", "toolchain") and name not in seen:
            seen.add(name)
            packages.append({"name": name, "current_version": version, "ecosystem": "Go"})

    # Single-line: require github.com/foo/bar v1.2.3
    for m in re.finditer(
        r"^require\s+([\w.\-/]+)\s+(v[\w.\-+]+)",
        content,
        re.MULTILINE,
    ):
        _add(m.group(1).strip(), m.group(2).strip())

    # Block-style:
    #   require (
    #       github.com/foo/bar v1.2.3
    #   )
    for m in re.finditer(
        r"^\s+([\w.\-/]+)\s+(v[\w.\-+]+)",
        content,
        re.MULTILINE,
    ):
        _add(m.group(1).strip(), m.group(2).strip())
    return packages


# ─── Java parsers (Maven + Gradle) ───────────────────────────────────────────

_MAVEN_NS = "http://maven.apache.org/POM/4.0.0"


def parse_pom_xml(path: Path) -> list[dict]:
    packages = []
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}") from e
    root = tree.getroot()

    # pom.xml may or may not have the Maven namespace
    ns = _MAVEN_NS if root.tag.startswith("{") else ""
    tag = lambda t: f"{{{ns}}}{t}" if ns else t  # noqa: E731

    for dep in root.iter(tag("dependency")):
        group = (dep.findtext(tag("groupId")) or "").strip()
        artifact = (dep.findtext(tag("artifactId")) or "").strip()
        version = (dep.findtext(tag("version")) or "").strip() or None

        if not group or not artifact:
            continue
        # Skip property placeholders like ${spring.version}
        if version and version.startswith("${"):
            version = None

        packages.append(
            {
                "name": f"{group}:{artifact}",
                "current_version": version,
                "ecosystem": "Maven",
            }
        )
    return packages


def parse_build_gradle(path: Path) -> list[dict]:
    """
    Parse Groovy or Kotlin Gradle build files.
    Handles common declaration styles:
      implementation 'group:artifact:version'
      implementation("group:artifact:version")
      testImplementation "group:artifact:version"
    """
    packages = []
    content = path.read_text(encoding="utf-8")
    # Match group:artifact:version inside quotes
    for m in re.finditer(r"""['"]([\w.\-]+):([\w.\-]+):([\w.\-]+)['"]""", content):
        group, artifact, version = m.group(1), m.group(2), m.group(3)
        packages.append(
            {
                "name": f"{group}:{artifact}",
                "current_version": version,
                "ecosystem": "Maven",
            }
        )
    return packages


# ─── C++ parsers (Conan + vcpkg) ─────────────────────────────────────────────


def parse_conanfile_txt(path: Path) -> list[dict]:
    """Parse Conan conanfile.txt [requires] section."""
    packages = []
    in_requires = False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("["):
            in_requires = line.lower() == "[requires]"
            continue
        if not in_requires or not line or line.startswith("#"):
            continue
        # Format: package/version[@channel] or package/version#revision
        m = re.match(r"^([\w.\-]+)/([\w.\-]+)", line)
        if m:
            packages.append(
                {
                    "name": m.group(1),
                    "current_version": m.group(2),
                    "ecosystem": "ConanCenter",
                }
            )
    return packages


def parse_conanfile_py(path: Path) -> list[dict]:
    """
    Parse Python-style conanfile.py for requires declarations.
    Supports common patterns; complex dynamic requires are skipped.
    """
    packages = []
    content = path.read_text(encoding="utf-8")
    # Match: "pkg/version" or 'pkg/version' inside requires = ... or self.requires(...)
    for m in re.finditer(r"""['"]([\w.\-]+)/([\w.\-]+)(?:@[^'"]*)?['"]""", content):
        packages.append(
            {
                "name": m.group(1),
                "current_version": m.group(2),
                "ecosystem": "ConanCenter",
            }
        )
    return packages


def parse_vcpkg_json(path: Path) -> list[dict]:
    """
    Parse vcpkg.json dependencies.
    Note: vcpkg is not in OSV — vulnerability checking is not available.
    Version data is parsed where present.
    """
    packages = []
    data = json.loads(path.read_text(encoding="utf-8"))
    for dep in data.get("dependencies", []):
        if isinstance(dep, str):
            packages.append({"name": dep, "current_version": None, "ecosystem": "vcpkg"})
        elif isinstance(dep, dict):
            name = dep.get("name", "")
            version = dep.get("version") or dep.get("version>=") or None
            if name:
                packages.append({"name": name, "current_version": version, "ecosystem": "vcpkg"})
    return packages


# ─── Registry API calls ───────────────────────────────────────────────────────


def get_pypi_latest(name: str) -> str | None:
    """Return the latest version string from PyPI, or None if the request fails."""
    data = _http(f"https://pypi.org/pypi/{name}/json")
    return data["info"]["version"] if data else None


def get_npm_latest(name: str) -> str | None:
    """Return the latest version string from the npm registry, or None if the request fails."""
    # Scoped packages like @types/node need URL encoding
    data = _http(f"https://registry.npmjs.org/{quote(name, safe='@/')}/latest")
    return data.get("version") if data else None


def _go_escape(module: str) -> str:
    """Encode Go module path for proxy API: uppercase letters → !lowercase."""
    return re.sub(r"[A-Z]", lambda m: "!" + m.group().lower(), module)


def get_go_latest(module: str) -> str | None:
    """Return the latest version for a Go module via the Go module proxy, or None on failure."""
    escaped = _go_escape(module)
    data = _http(f"https://proxy.golang.org/{escaped}/@latest")
    return data.get("Version") if data else None


def get_maven_latest(group_artifact: str) -> str | None:
    """Query Maven Central Search API for latest version of group:artifact."""
    parts = group_artifact.split(":", 1)
    if len(parts) != 2:
        return None
    group, artifact = parts
    url = (
        f"https://search.maven.org/solrsearch/select"
        f"?q=g:{quote(group)}+AND+a:{quote(artifact)}&rows=1&wt=json"
    )
    data = _http(url)
    try:
        return data["response"]["docs"][0]["latestVersion"]  # type: ignore[index]
    except (TypeError, KeyError, IndexError):
        return None


def get_osv_vulnerabilities(name: str, version: str | None, ecosystem: str) -> list[dict]:
    """Query OSV (osv.dev) for known vulnerabilities. Free, no key required."""
    osv_eco = OSV_ECOSYSTEM.get(ecosystem)
    if not osv_eco:
        return []  # Ecosystem not supported by OSV

    payload: dict[str, Any] = {"package": {"name": name, "ecosystem": osv_eco}}
    if version:
        payload["version"] = version

    data = _http(
        "https://api.osv.dev/v1/query",
        method="POST",
        body=json.dumps(payload).encode(),
    )
    if not data or "vulns" not in data:
        return []

    results = []
    for vuln in data["vulns"][:5]:
        db = vuln.get("database_specific", {})
        severity = db.get("severity", "UNKNOWN").upper()
        if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            severity = "UNKNOWN"
        results.append(
            {
                "id": vuln.get("id", "UNKNOWN"),
                "summary": (vuln.get("summary") or "No description")[:200],
                "severity": severity,
                "url": f"https://osv.dev/vulnerability/{vuln.get('id', '')}",
            }
        )
    return results


# ─── Per-package audit ────────────────────────────────────────────────────────

def _audit_one(pkg: dict) -> dict:
    """
    Audit a single package: fetch its latest version and check OSV for vulnerabilities.

    Returns a result dict with keys: package, current_version, latest_version, outdated, vulnerable, vulnerabilities.
    """
    name = pkg["name"]
    current = pkg["current_version"]
    ecosystem = pkg["ecosystem"]

    # Built inside the function so that module-level patches (e.g. in tests) are
    # picked up at call time rather than being frozen at module load time.
    _latest_fn: dict[str, Any] = {
        "PyPI": get_pypi_latest,
        "npm": get_npm_latest,
        "Go": get_go_latest,
        "Maven": get_maven_latest,
        # Conan and vcpkg have no reliable public version API
        "ConanCenter": lambda _: None,
        "vcpkg": lambda _: None,
    }
    latest = _latest_fn.get(ecosystem, lambda _: None)(name)
    vulns = get_osv_vulnerabilities(name, current, ecosystem)

    # For Go, versions have a "v" prefix — strip for comparison
    current_cmp = current.lstrip("v") if current else None
    latest_cmp = latest.lstrip("v") if latest else None
    outdated = bool(current_cmp and latest_cmp and current_cmp != latest_cmp)

    vuln_note = None
    if ecosystem == "vcpkg":
        vuln_note = "Vulnerability data not available for vcpkg packages"
    elif ecosystem == "ConanCenter" and not latest:
        vuln_note = "Version registry unavailable for Conan — vulnerability check ran against declared version"

    result: dict[str, Any] = {
        "package": name,
        "current_version": current or "unpinned",
        "latest_version": latest or "unknown",
        "outdated": outdated,
        "vulnerable": len(vulns) > 0,
        "vulnerabilities": vulns,
    }
    if vuln_note:
        result["note"] = vuln_note
    return result


# ─── File discovery ───────────────────────────────────────────────────────────

DEPENDENCY_FILES: list[tuple[str, Any]] = [
    # Python
    ("requirements.txt", parse_requirements_txt),
    ("pyproject.toml", parse_pyproject_toml),
    ("Pipfile", parse_pipfile),
    # JavaScript / TypeScript / React / Next.js / Vue
    ("package.json", parse_package_json),
    # Go
    ("go.mod", parse_go_mod),
    # Java
    ("pom.xml", parse_pom_xml),
    ("build.gradle", parse_build_gradle),
    ("build.gradle.kts", parse_build_gradle),
    # C++
    ("conanfile.txt", parse_conanfile_txt),
    ("conanfile.py", parse_conanfile_py),
    ("vcpkg.json", parse_vcpkg_json),
]

ALL_GROUPS = ["python", "javascript", "go", "java", "cpp"]


# ─── Entrypoint ───────────────────────────────────────────────────────────────


def run(params: dict[str, Any]) -> dict[str, Any]:
    """
    MCP entrypoint for dependency_audit.

    Params:
        path  Path to a project directory containing dependency files (default: ".")

    Discovers dependency files (requirements.txt, pyproject.toml, package.json, go.mod, pom.xml,
    build.gradle, conanfile.txt/py, vcpkg.json), audits each package concurrently against the
    relevant version registry and the OSV vulnerability database, and returns a grouped summary.

    Returns {"result": {...}, "error": None} on success or {"result": None, "error": "..."} on failure.
    """
    path_str = params.get("path", ".")
    root = Path(path_str).expanduser().resolve()

    if not root.exists():
        return {"result": None, "error": f"Path does not exist: {path_str}"}
    if not root.is_dir():
        return {"result": None, "error": f"Path is not a directory: {path_str}"}

    all_packages: list[dict] = []
    files_scanned: list[str] = []
    parse_errors: list[str] = []

    for filename, parser in DEPENDENCY_FILES:
        candidate = root / filename
        if not candidate.exists():
            continue
        files_scanned.append(filename)
        try:
            pkgs = parser(candidate)
            all_packages.extend(pkgs)
        except Exception as e:
            parse_errors.append(f"{filename}: {e}")

    if not files_scanned and not parse_errors:
        supported = ", ".join(f for f, _ in DEPENDENCY_FILES)
        return {"result": None, "error": f"No dependency files found. Looked for: {supported}"}

    # Deduplicate by (name, ecosystem)
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for pkg in all_packages:
        key = (pkg["name"], pkg["ecosystem"])
        if key not in seen:
            seen.add(key)
            unique.append(pkg)

    # Audit concurrently
    grouped: dict[str, list[dict]] = {g: [] for g in ALL_GROUPS}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_audit_one, pkg): pkg for pkg in unique}
        for future in as_completed(futures):
            try:
                result = future.result()
                group = ECOSYSTEM_GROUP.get(futures[future]["ecosystem"], "other")
                grouped.setdefault(group, []).append(result)
            except Exception as e:
                pkg = futures[future]
                parse_errors.append(f"{pkg['name']} ({pkg['ecosystem']}): audit failed — {e}")

    def _sort(r: dict) -> tuple:
        return (not r["vulnerable"], not r["outdated"], r["package"])

    for group in grouped.values():
        group.sort(key=_sort)

    all_results = [r for group in grouped.values() for r in group]
    total = len(all_results)
    n_vulnerable = sum(1 for r in all_results if r["vulnerable"])
    n_outdated = sum(1 for r in all_results if r["outdated"])
    n_ok = sum(1 for r in all_results if not r["outdated"] and not r["vulnerable"])

    result: dict[str, Any] = {
        "path": str(root),
        "files_scanned": files_scanned,
        "summary": {
            "total": total,
            "vulnerable": n_vulnerable,
            "outdated": n_outdated,
            "up_to_date": n_ok,
        },
        "findings": {g: v for g, v in grouped.items() if v},
    }

    if parse_errors:
        result["parse_errors"] = parse_errors

    return {"result": result, "error": None}
