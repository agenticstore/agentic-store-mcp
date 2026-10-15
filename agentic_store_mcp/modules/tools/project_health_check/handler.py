"""Read-only project inventory for agent task setup and validation planning."""
import json
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any


_MANIFESTS = (
    "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "uv.lock",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
)
_RUNTIMES = {
    "python": ["python3", "--version"],
    "node": ["node", "--version"],
    "go": ["go", "version"],
    "rust": ["rustc", "--version"],
    "java": ["java", "--version"],
    "docker": ["docker", "--version"],
}


def _command_output(args: list[str]) -> str | None:
    if not shutil.which(args[0]):
        return None
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=4)
        output = (completed.stdout or completed.stderr).strip().splitlines()
        return output[0] if completed.returncode == 0 and output else None
    except (OSError, subprocess.SubprocessError):
        return None


def _git(path: Path, *args: str) -> str | None:
    if not shutil.which("git"):
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True, timeout=5,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _package_scripts(path: Path) -> dict[str, str]:
    package_json = path / "package.json"
    if not package_json.is_file():
        return {}
    try:
        scripts = json.loads(package_json.read_text(encoding="utf-8")).get("scripts", {})
        return {str(name): str(value) for name, value in scripts.items() if isinstance(value, str)}
    except (OSError, ValueError):
        return {}


def _python_scripts(path: Path) -> list[str]:
    pyproject = path / "pyproject.toml"
    if not pyproject.is_file():
        return []
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return sorted((data.get("project", {}).get("scripts") or {}).keys())
    except (OSError, tomllib.TOMLDecodeError):
        return []


def _detected_stacks(manifests: list[str]) -> list[str]:
    stacks: list[str] = []
    if any(name in manifests for name in ("pyproject.toml", "requirements.txt", "Pipfile")):
        stacks.append("python")
    if "package.json" in manifests:
        stacks.append("node")
    if "go.mod" in manifests:
        stacks.append("go")
    if "Cargo.toml" in manifests:
        stacks.append("rust")
    if any(name in manifests for name in ("pom.xml", "build.gradle", "build.gradle.kts")):
        stacks.append("java")
    if any(name in manifests for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")):
        stacks.append("docker")
    return stacks


def run(params: dict[str, Any]) -> dict[str, Any]:
    requested_path = str(params.get("path") or "").strip()
    if not requested_path:
        return {"result": None, "error": "'path' is required"}

    project = Path(requested_path).expanduser().resolve()
    if not project.exists():
        return {"result": None, "error": f"Directory not found: {project}"}
    if not project.is_dir():
        return {"result": None, "error": f"Path is not a directory: {project}"}

    manifests = [name for name in _MANIFESTS if (project / name).is_file()]
    stacks = _detected_stacks(manifests)
    package_scripts = _package_scripts(project)
    python_scripts = _python_scripts(project)
    git_root = _git(project, "rev-parse", "--show-toplevel")
    git_status = _git(project, "status", "--porcelain") if git_root else None
    branch = _git(project, "branch", "--show-current") if git_root else None

    runtimes: dict[str, dict[str, Any]] = {}
    if params.get("include_runtime_versions", True):
        for name in stacks:
            runtime = _RUNTIMES.get(name)
            if runtime:
                runtimes[name] = {"available": bool(shutil.which(runtime[0])), "version": _command_output(runtime)}

    checks: list[dict[str, str]] = []
    if git_root and git_status:
        checks.append({"level": "warning", "code": "git_dirty", "message": "Git working tree has uncommitted changes."})
    if "python" in stacks and not any(name in manifests for name in ("uv.lock", "poetry.lock", "requirements.txt")):
        checks.append({"level": "info", "code": "python_lock_missing", "message": "No Python lockfile or requirements.txt detected."})
    if "node" in stacks and not any(name in manifests for name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")):
        checks.append({"level": "info", "code": "node_lock_missing", "message": "No Node.js lockfile detected."})
    if (project / ".env.example").is_file() and not (project / ".env").exists():
        checks.append({"level": "info", "code": "env_not_created", "message": ".env.example exists but .env is not present."})

    return {
        "result": {
            "path": str(project),
            "project_name": project.name,
            "stacks": stacks,
            "manifests": manifests,
            "git": {
                "is_repository": bool(git_root),
                "root": git_root,
                "branch": branch or None,
                "dirty": bool(git_status) if git_root else None,
            },
            "runtimes": runtimes,
            "declared_commands": {
                "node_scripts": package_scripts,
                "python_entry_points": python_scripts,
                "recommended": _recommended_commands(manifests, package_scripts),
            },
            "checks": checks,
            "read_only": True,
        },
        "error": None,
    }


def _recommended_commands(manifests: list[str], scripts: dict[str, str]) -> list[str]:
    commands: list[str] = []
    if "pyproject.toml" in manifests:
        commands.append("uv run pytest")
    elif "requirements.txt" in manifests:
        commands.append("pytest")
    for script in ("test", "lint", "build"):
        if script in scripts:
            commands.append(f"npm run {script}")
    if "go.mod" in manifests:
        commands.append("go test ./...")
    if "Cargo.toml" in manifests:
        commands.append("cargo test")
    return commands
