"""
list_processes — check whether named services are running on the local machine.

Uses pgrep, lsof, and docker CLI. No external Python packages required.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

# ─── Well-known service definitions ──────────────────────────────────────────
# Each entry: process_names (pgrep patterns), default_ports, port_protocol

_KNOWN_SERVICES: dict[str, dict[str, Any]] = {
    # ── Container / VM runtimes ───────────────────────────────────────────────
    "docker":       {"patterns": ["docker", "dockerd"],            "ports": [2375, 2376]},
    "dockerd":      {"patterns": ["dockerd"],                      "ports": [2375, 2376]},

    # ── Databases ─────────────────────────────────────────────────────────────
    "redis":        {"patterns": ["redis-server"],                 "ports": [6379]},
    "postgres":     {"patterns": ["postgres", "postgresql"],       "ports": [5432]},
    "mysql":        {"patterns": ["mysqld"],                       "ports": [3306]},
    "mongodb":      {"patterns": ["mongod"],                       "ports": [27017]},

    # ── Web servers / proxies ─────────────────────────────────────────────────
    "nginx":        {"patterns": ["nginx"],                        "ports": [80, 443]},

    # ── Language runtimes ─────────────────────────────────────────────────────
    "node":         {"patterns": ["node"],                         "ports": []},
    "python":       {"patterns": ["python", "python3"],            "ports": []},

    # ── Python app servers / workers ──────────────────────────────────────────
    "uvicorn":      {"patterns": ["uvicorn"],                      "ports": [8000, 8080]},
    "celery":       {"patterns": ["celery"],                       "ports": []},
    "flower":       {"patterns": ["flower"],                       "ports": [5555]},

    # ── Message brokers ───────────────────────────────────────────────────────
    "rabbitmq":     {"patterns": ["beam.smp", "rabbitmq"],         "ports": [5672, 15672]},

    # ── Version control / agents ──────────────────────────────────────────────
    "git":          {"patterns": ["git", "git-daemon"],            "ports": [9418]},
    "ssh-agent":    {"patterns": ["ssh-agent"],                    "ports": []},
    "gpg-agent":    {"patterns": ["gpg-agent"],                    "ports": []},

    # ── Node.js dev tools ─────────────────────────────────────────────────────
    "nodemon":      {"patterns": ["nodemon"],                      "ports": []},
    "watchman":     {"patterns": ["watchman"],                     "ports": []},
    "vite":         {"patterns": ["vite"],                         "ports": [5173, 4173]},
    "webpack":      {"patterns": ["webpack"],                      "ports": [8080]},
    "esbuild":      {"patterns": ["esbuild"],                      "ports": []},

    # ── Test runners ──────────────────────────────────────────────────────────
    "pytest":       {"patterns": ["pytest", "py.test"],            "ports": []},
    "jest":         {"patterns": ["jest"],                         "ports": []},
    "vitest":       {"patterns": ["vitest"],                       "ports": [51204]},

    # ── Linters / formatters (often run as daemons/watchers) ──────────────────
    "eslint":       {"patterns": ["eslint"],                       "ports": []},
    "prettier":     {"patterns": ["prettier"],                     "ports": []},

    # ── Observability stack ───────────────────────────────────────────────────
    "prometheus":   {"patterns": ["prometheus"],                   "ports": [9090]},
    "grafana":      {"patterns": ["grafana", "grafana-server"],    "ports": [3000]},
    "jaeger":       {"patterns": ["jaeger", "jaeger-all-in-one"],  "ports": [16686, 14268]},
    "zipkin":       {"patterns": ["zipkin"],                       "ports": [9411]},
    "opentelemetry-collector": {
                    "patterns": ["otelcol", "otelcol-contrib"],    "ports": [4317, 4318]},

    # ── Tunnels ───────────────────────────────────────────────────────────────
    "ngrok":        {"patterns": ["ngrok"],                        "ports": [4040]},
    "cloudflared":  {"patterns": ["cloudflared"],                  "ports": []},

    # ── System / scheduling ───────────────────────────────────────────────────
    "cron":         {"patterns": ["cron", "crond"],                "ports": []},

    # ── Secrets / security ────────────────────────────────────────────────────
    "vault":        {"patterns": ["vault"],                        "ports": [8200]},
}


# ─── Process detection ────────────────────────────────────────────────────────

def _pgrep(pattern: str) -> list[int]:
    """Return list of PIDs matching the pattern."""
    if not shutil.which("pgrep"):
        return _ps_grep(pattern)
    try:
        result = subprocess.run(
            ["pgrep", "-x", pattern],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return [int(p) for p in result.stdout.splitlines() if p.strip().isdigit()]
    except Exception:
        pass
    return []


def _ps_grep(pattern: str) -> list[int]:
    """Fallback: grep through `ps aux` output."""
    try:
        ps = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
        pids = []
        for line in ps.stdout.splitlines()[1:]:
            cols = line.split()
            if len(cols) > 10 and re.search(rf"\b{re.escape(pattern)}\b", cols[10]):
                try:
                    pids.append(int(cols[1]))
                except ValueError:
                    pass
        return pids
    except Exception:
        return []


def _listening_ports(pid: int) -> list[int]:
    """Return ports PID is listening on via lsof."""
    if not shutil.which("lsof"):
        return []
    try:
        result = subprocess.run(
            ["lsof", "-Pan", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=4,
        )
        ports = []
        for line in result.stdout.splitlines()[1:]:
            m = re.search(r":(\d+)\s+\(LISTEN\)", line)
            if m:
                ports.append(int(m.group(1)))
        return sorted(set(ports))
    except Exception:
        return []


def _check_port(port: int) -> bool:
    """Check if a port is listening using lsof (no socket creation)."""
    if not shutil.which("lsof"):
        return False
    try:
        r = subprocess.run(
            ["lsof", "-i", f"TCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=3,
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


def _docker_status() -> dict[str, Any]:
    """Special-case Docker: check daemon + container count."""
    if not shutil.which("docker"):
        return {"running": False, "note": "docker CLI not found"}
    try:
        r = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=4,
        )
        if r.returncode == 0 and r.stdout.strip():
            # Count running containers
            ps = subprocess.run(
                ["docker", "ps", "-q"],
                capture_output=True, text=True, timeout=4,
            )
            container_count = len([l for l in ps.stdout.splitlines() if l.strip()])
            return {
                "running": True,
                "daemon_version": r.stdout.strip(),
                "running_containers": container_count,
            }
    except Exception:
        pass
    return {"running": False}


# ─── Entry point ─────────────────────────────────────────────────────────────

def run(params: dict) -> dict:
    services_req = params.get("services") or []
    include_ports = bool(params.get("include_ports", True))

    # Resolve requested service names
    if services_req:
        # Support "port:3000" syntax and custom names
        to_check: list[str] = []
        port_checks: list[int] = []
        for s in services_req:
            s = str(s).strip().lower()
            if s.startswith("port:"):
                try:
                    port_checks.append(int(s.split(":", 1)[1]))
                except ValueError:
                    pass
            else:
                to_check.append(s)
    else:
        to_check = list(_KNOWN_SERVICES.keys())
        port_checks = []

    try:
        results: dict[str, Any] = {}

        for name in to_check:
            if name == "docker":
                info = _docker_status()
                entry: dict[str, Any] = {
                    "running": info.get("running", False),
                    "pids": [],
                }
                if info.get("running"):
                    entry["daemon_version"] = info.get("daemon_version")
                    entry["running_containers"] = info.get("running_containers", 0)
                results["docker"] = entry
                continue

            defn = _KNOWN_SERVICES.get(name)
            patterns = defn["patterns"] if defn else [name]
            default_ports = defn["ports"] if defn else []

            pids: list[int] = []
            for pat in patterns:
                pids.extend(_pgrep(pat))
            pids = sorted(set(pids))

            entry = {"running": bool(pids), "pids": pids}

            if include_ports and pids:
                all_ports: list[int] = []
                for pid in pids[:3]:  # cap at 3 PIDs to avoid slow lsof on many PIDs
                    all_ports.extend(_listening_ports(pid))
                entry["listening_ports"] = sorted(set(all_ports))
            elif include_ports and default_ports:
                # No running PID — check whether well-known ports are open anyway
                open_ports = [p for p in default_ports if _check_port(p)]
                if open_ports:
                    entry["running"] = True
                    entry["listening_ports"] = open_ports
                    entry["note"] = "Detected via port — no matching process name found"

            results[name] = entry

        # Handle port:N requests
        for port in port_checks:
            key = f"port:{port}"
            listening = _check_port(port)
            results[key] = {"running": listening, "port": port}

        running_count = sum(1 for v in results.values() if v.get("running"))

        return {
            "result": {
                "services": results,
                "running_count": running_count,
                "checked_count": len(results),
            },
            "error": None,
        }

    except Exception as e:
        return {"result": None, "error": str(e)}
