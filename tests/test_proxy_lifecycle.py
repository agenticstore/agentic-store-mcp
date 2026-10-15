"""The macOS proxy must never outlive its local listener."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agentic_store_mcp.firewall import system_proxy, tls_proxy, watchdog
from agentic_store_mcp.webapp import app as webapp


def test_system_proxy_restores_prior_state_and_disabled_legacy(tmp_path, monkeypatch):
    monkeypatch.setattr(system_proxy, "SNAPSHOT_FILE", tmp_path / "proxy.json")
    state = {
        ("Wi-Fi", "web"): {
            "enabled": True,
            "server": "proxy.example",
            "port": "3128",
            "authenticated": False,
        },
        ("Wi-Fi", "secure"): {
            "enabled": False,
            "server": "",
            "port": "0",
            "authenticated": False,
        },
        ("Ethernet", "web"): {
            "enabled": True,
            "server": "127.0.0.1",
            "port": "8766",
            "authenticated": False,
        },
        ("Ethernet", "secure"): {
            "enabled": False,
            "server": "",
            "port": "0",
            "authenticated": False,
        },
    }
    monkeypatch.setattr(
        system_proxy, "_get_network_services", lambda: ["Wi-Fi", "Ethernet"]
    )
    monkeypatch.setattr(
        system_proxy,
        "_read_proxy",
        lambda service, secure: dict(state[service, "secure" if secure else "web"]),
    )
    calls = []
    monkeypatch.setattr(system_proxy, "_networksetup", lambda *args: calls.append(args))
    assert system_proxy.set_system_proxy(8766) == ["Wi-Fi", "Ethernet"]
    assert system_proxy.SNAPSHOT_FILE.exists()
    system_proxy.remove_system_proxy(8766)
    assert not system_proxy.SNAPSHOT_FILE.exists()
    assert ("-setwebproxy", "Wi-Fi", "proxy.example", "3128") in calls
    assert ("-setwebproxystate", "Wi-Fi", "on") in calls
    assert ("-setwebproxystate", "Ethernet", "off") in calls


def test_system_proxy_rolls_back_partial_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(system_proxy, "SNAPSHOT_FILE", tmp_path / "proxy.json")
    monkeypatch.setattr(system_proxy, "_get_network_services", lambda: ["Wi-Fi"])
    monkeypatch.setattr(
        system_proxy,
        "_read_proxy",
        lambda *args: {
            "enabled": False,
            "server": "",
            "port": "0",
            "authenticated": False,
        },
    )
    calls = []

    def command(*args):
        calls.append(args)
        if args[0] == "-setsecurewebproxy":
            raise RuntimeError("denied")

    monkeypatch.setattr(system_proxy, "_networksetup", command)
    with pytest.raises(RuntimeError, match="denied"):
        system_proxy.set_system_proxy()
    assert ("-setwebproxystate", "Wi-Fi", "off") in calls
    assert not system_proxy.SNAPSHOT_FILE.exists()


def test_shutdown_restores_route_before_stopping_listener(monkeypatch):
    calls = []

    async def stop():
        calls.append("http_stop")

    async def startup():
        pass

    monkeypatch.setattr(webapp, "_auto_restore_proxy", startup)
    monkeypatch.setattr(webapp, "_setup_sleep_wake", lambda: None)
    monkeypatch.setattr(
        system_proxy, "remove_system_proxy", lambda port=8766: calls.append("restore")
    )
    monkeypatch.setattr(tls_proxy, "stop_tls_proxy", lambda: calls.append("tls_stop"))
    with (
        patch("agentic_store_mcp.firewall.proxy.stop_proxy", stop),
        patch(
            "agentic_store_mcp.firewall.rules.load_config", return_value={"port": 8766}
        ),
        patch("subprocess.run"),
    ):
        with TestClient(webapp.app):
            pass
    assert calls.index("restore") < calls.index("http_stop") < calls.index("tls_stop")


def test_tls_startup_failure_does_not_route_machine(tmp_path, monkeypatch):
    monkeypatch.setattr(tls_proxy, "CONFDIR", tmp_path)
    with (
        patch.object(tls_proxy, "DumpMaster", side_effect=RuntimeError("bad loop")),
        patch.object(system_proxy, "remove_system_proxy"),
        patch.object(tls_proxy.socket, "socket"),
    ):
        with pytest.raises(RuntimeError, match="bad loop"):
            tls_proxy.start_tls_proxy(0)


def test_watchdog_restores_when_parent_disappears(tmp_path, monkeypatch):
    import json

    snapshot = tmp_path / "proxy.json"
    snapshot.write_text(json.dumps({"_owner_pid": 123}))
    monkeypatch.setattr(watchdog, "SNAPSHOT_FILE", snapshot)
    monkeypatch.setattr(watchdog.sys, "argv", ["watchdog", "123", "8766"])
    monkeypatch.setattr(watchdog, "_parent_alive", lambda pid: False)
    restored = []

    def restore(port):
        restored.append(port)
        snapshot.unlink()

    monkeypatch.setattr(watchdog, "remove_system_proxy", restore)
    watchdog.main()
    assert restored == [8766]


def test_install_starts_listener_before_system_routing(monkeypatch):
    calls = []

    async def startup():
        pass

    async def stop():
        pass

    monkeypatch.setattr(webapp, "_auto_restore_proxy", startup)
    monkeypatch.setattr(webapp, "_setup_sleep_wake", lambda: None)
    with (
        patch("agentic_store_mcp.firewall.ca_manager.ensure_ca_generated"),
        patch(
            "agentic_store_mcp.firewall.ca_manager.is_ca_installed", return_value=True
        ),
        patch(
            "agentic_store_mcp.firewall.tls_proxy.start_tls_proxy",
            side_effect=lambda port: calls.append("tls"),
        ),
        patch(
            "agentic_store_mcp.firewall.system_proxy.set_system_proxy",
            side_effect=lambda port: calls.append("network") or ["Wi-Fi"],
        ),
        patch(
            "agentic_store_mcp.firewall.watchdog.start_watchdog",
            side_effect=lambda port: calls.append("watchdog"),
        ),
        patch(
            "agentic_store_mcp.firewall.rules.load_config", return_value={"port": 8766}
        ),
        patch("agentic_store_mcp.firewall.rules.save_config"),
        patch("agentic_store_mcp.firewall.audit.log_event"),
        patch("agentic_store_mcp.firewall.system_proxy.remove_system_proxy"),
        patch("agentic_store_mcp.firewall.tls_proxy.stop_tls_proxy"),
        patch("agentic_store_mcp.firewall.proxy.stop_proxy", stop),
        patch("subprocess.run"),
    ):
        with TestClient(webapp.app) as client:
            response = client.post("/api/firewall/system/install")
    assert response.status_code == 200
    assert calls == ["tls", "network", "watchdog"]
