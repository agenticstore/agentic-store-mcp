import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

HANDLER = Path(__file__).parent / "handler.py"


def load():
    spec = importlib.util.spec_from_file_location("handler", HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mock_pgrep_found(pattern):
    return [1234]


def _mock_pgrep_empty(pattern):
    return []


def test_default_all_services_structure():
    h = load()
    with patch.object(h, "_pgrep", return_value=[]):
        with patch.object(h, "_check_port", return_value=False):
            with patch.object(h, "_docker_status", return_value={"running": False}):
                r = h.run({})
    assert r["error"] is None
    assert "services" in r["result"]
    assert r["result"]["checked_count"] == len(h._KNOWN_SERVICES)


def test_specific_service_running():
    h = load()
    with patch.object(h, "_pgrep", return_value=[9999]):
        with patch.object(h, "_listening_ports", return_value=[6379]):
            r = h.run({"services": ["redis"]})
    assert r["error"] is None
    assert r["result"]["services"]["redis"]["running"] is True
    assert r["result"]["services"]["redis"]["pids"] == [9999]
    assert 6379 in r["result"]["services"]["redis"]["listening_ports"]


def test_service_not_running():
    h = load()
    with patch.object(h, "_pgrep", return_value=[]):
        with patch.object(h, "_check_port", return_value=False):
            r = h.run({"services": ["redis"]})
    assert r["error"] is None
    assert r["result"]["services"]["redis"]["running"] is False


def test_port_syntax():
    h = load()
    with patch.object(h, "_check_port", return_value=True):
        r = h.run({"services": ["port:3000"]})
    assert r["error"] is None
    assert r["result"]["services"]["port:3000"]["running"] is True


def test_docker_running():
    h = load()
    with patch.object(h, "_docker_status", return_value={
        "running": True, "daemon_version": "24.0.1", "running_containers": 3
    }):
        r = h.run({"services": ["docker"]})
    assert r["error"] is None
    d = r["result"]["services"]["docker"]
    assert d["running"] is True
    assert d["running_containers"] == 3


def test_include_ports_false():
    h = load()
    with patch.object(h, "_pgrep", return_value=[1234]):
        with patch.object(h, "_listening_ports") as mock_lsof:
            r = h.run({"services": ["redis"], "include_ports": False})
            mock_lsof.assert_not_called()
    assert r["error"] is None


def test_unknown_custom_service():
    h = load()
    with patch.object(h, "_pgrep", return_value=[5678]):
        with patch.object(h, "_listening_ports", return_value=[]):
            r = h.run({"services": ["myapp"]})
    assert r["error"] is None
    assert r["result"]["services"]["myapp"]["running"] is True
