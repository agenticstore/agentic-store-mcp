"""macOS system-level HTTPS proxy configuration via networksetup."""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable

SNAPSHOT_FILE = Path.home() / ".config" / "agentic-store" / "system_proxy_snapshot.json"


def _get_network_services() -> list[str]:
    result = subprocess.run(
        ["networksetup", "-listallnetworkservices"], capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(f"Could not list network services: {result.stderr.strip()}")
    services = []
    for line in result.stdout.splitlines():
        line = line.strip()
        # Skip empty lines, disabled services (*), and the header/disclaimer sentence
        if not line or line.startswith("*") or "network service" in line.lower():
            continue
        services.append(line)
    return services


def _networksetup(*args: str) -> str:
    result = subprocess.run(["networksetup", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(
            f"networksetup failed for {args[0]}: {result.stderr.strip()}"
        )
    return result.stdout


def _read_proxy(service: str, secure: bool) -> dict:
    command = "-getsecurewebproxy" if secure else "-getwebproxy"
    values = {}
    for line in _networksetup(command, service).splitlines():
        key, _, value = line.partition(": ")
        values[key] = value.strip()
    return {
        "enabled": values.get("Enabled") == "Yes",
        "server": values.get("Server", ""),
        "port": values.get("Port", "0"),
        "authenticated": values.get("Authenticated Proxy Enabled") in ("1", "Yes"),
    }


def _save_snapshot(snapshot: dict) -> None:
    SNAPSHOT_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = SNAPSHOT_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)
    os.replace(tmp, SNAPSHOT_FILE)


def set_system_proxy(port: int = 8766) -> list[str]:
    """Save prior settings, then route HTTP and HTTPS through our live proxy."""
    services = _get_network_services()
    if not services:
        raise RuntimeError("No network services are available")
    if not SNAPSHOT_FILE.exists():
        snapshot = {}
        for service in services:
            snapshot[service] = {
                "web": _read_proxy(service, False),
                "secure": _read_proxy(service, True),
            }
            for setting in snapshot[service].values():
                if setting["authenticated"]:
                    raise RuntimeError(
                        "An authenticated system proxy is already configured; refusing to replace it"
                    )
                # Older AgenticStore versions left localhost routing behind.
                # Never save that stale address as the user's prior state.
                if setting["server"] == "127.0.0.1" and setting["port"] == str(port):
                    setting["enabled"] = False
        _save_snapshot(snapshot)
    else:
        snapshot = json.loads(SNAPSHOT_FILE.read_text())
    snapshot["_owner_pid"] = os.getpid()
    _save_snapshot(snapshot)
    try:
        for service in services:
            _networksetup("-setwebproxy", service, "127.0.0.1", str(port))
            _networksetup("-setsecurewebproxy", service, "127.0.0.1", str(port))
            _networksetup("-setwebproxystate", service, "on")
            _networksetup("-setsecurewebproxystate", service, "on")
    except Exception:
        remove_system_proxy()
        raise
    return services


def remove_system_proxy(port: int = 8766) -> None:
    """Restore the captured settings; only disable our proxy on old installs."""
    snapshot = json.loads(SNAPSHOT_FILE.read_text()) if SNAPSHOT_FILE.exists() else {}
    errors = []
    services = _get_network_services()
    if snapshot and not services:
        raise RuntimeError("Cannot restore proxy settings without network services")
    for service in services:
        for secure, key in ((False, "web"), (True, "secure")):
            state = snapshot.get(service, {}).get(key)
            get_command = "-getsecurewebproxy" if secure else "-getwebproxy"
            set_command = "-setsecurewebproxy" if secure else "-setwebproxy"
            state_command = "-setsecurewebproxystate" if secure else "-setwebproxystate"
            try:
                if state:
                    if state["server"] and state["port"] not in ("", "0"):
                        _networksetup(
                            set_command, service, state["server"], state["port"]
                        )
                    _networksetup(
                        state_command, service, "on" if state["enabled"] else "off"
                    )
                else:
                    current = _read_proxy(service, secure)
                    if (
                        current["enabled"]
                        and current["server"] == "127.0.0.1"
                        and current["port"] == str(port)
                    ):
                        _networksetup(state_command, service, "off")
            except Exception as exc:
                errors.append(f"{service} {get_command}: {exc}")
    if errors:
        raise RuntimeError("Could not restore system proxy: " + "; ".join(errors))
    if SNAPSHOT_FILE.exists():
        SNAPSHOT_FILE.unlink()


def is_system_proxy_set(port: int = 8766) -> bool:
    """Check whether any service still routes through our local proxy."""
    services = _get_network_services()
    return any(
        (state := _read_proxy(service, secure))["enabled"]
        and state["server"] == "127.0.0.1"
        and state["port"] == str(port)
        for service in services
        for secure in (False, True)
    )


# Module-level ref so the C callback is never garbage-collected.
_sleep_wake_cb_ref: object = None

_kIOMessageSystemWillSleep = 0xE0000280
_kIOMessageSystemHasPoweredOn = 0xE0000300


def watch_sleep_wake(on_sleep: Callable[[], None], on_wake: Callable[[], None]) -> bool:
    """Register callbacks fired on macOS system sleep and wake.

    Uses IOKit directly via ctypes — no extra Python packages needed.
    Spins up a daemon thread with a CoreFoundation run loop.
    Returns True when successfully registered, False on non-macOS or any error.
    """
    global _sleep_wake_cb_ref
    try:
        iokit = ctypes.CDLL(
            ctypes.util.find_library("IOKit")
            or "/System/Library/Frameworks/IOKit.framework/IOKit"
        )
        cf = ctypes.CDLL(
            ctypes.util.find_library("CoreFoundation")
            or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
    except Exception:
        return False

    try:
        iokit.IORegisterForSystemPower.restype = ctypes.c_uint32
        iokit.IORegisterForSystemPower.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        iokit.IOAllowPowerChange.restype = ctypes.c_int
        iokit.IOAllowPowerChange.argtypes = [ctypes.c_uint32, ctypes.c_long]
        iokit.IONotificationPortGetRunLoopSource.restype = ctypes.c_void_p
        iokit.IONotificationPortGetRunLoopSource.argtypes = [ctypes.c_void_p]

        cf.CFRunLoopGetCurrent.restype = ctypes.c_void_p
        cf.CFRunLoopAddSource.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        cf.CFRunLoopRun.argtypes = []

        # kCFRunLoopDefaultMode is a CFStringRef global — read its pointer value.
        kCFRunLoopDefaultMode = ctypes.c_void_p.in_dll(
            cf, "kCFRunLoopDefaultMode"
        ).value
    except Exception:
        return False

    # Mutable state shared between the thread and the callback closure.
    _state: dict[str, int] = {"root_port": 0}

    _IOServiceInterestCallback = ctypes.CFUNCTYPE(
        None,
        ctypes.c_void_p,  # refcon
        ctypes.c_uint32,  # io_service_t (root port back-channel)
        ctypes.c_uint32,  # messageType
        ctypes.c_void_p,  # messageArgument (notification ID for IOAllowPowerChange)
    )

    def _callback(
        refcon: ctypes.c_void_p,
        service: int,
        message_type: int,
        message_argument: ctypes.c_void_p,
    ) -> None:
        if message_type == _kIOMessageSystemWillSleep:
            try:
                on_sleep()
            except Exception:
                pass
            # Must acknowledge the sleep notification or macOS will hang.
            try:
                iokit.IOAllowPowerChange(_state["root_port"], message_argument)
            except Exception:
                pass
        elif message_type == _kIOMessageSystemHasPoweredOn:
            try:
                on_wake()
            except Exception:
                pass

    cb = _IOServiceInterestCallback(_callback)
    _sleep_wake_cb_ref = cb  # keep alive — ctypes frees it otherwise

    def _run() -> None:
        notify_port = ctypes.c_void_p(0)
        notifier = ctypes.c_uint32(0)

        root_port = iokit.IORegisterForSystemPower(
            None,
            ctypes.byref(notify_port),
            cb,
            ctypes.byref(notifier),
        )
        if root_port == 0:
            return

        _state["root_port"] = root_port

        source = iokit.IONotificationPortGetRunLoopSource(notify_port)
        if not source:
            return

        cf.CFRunLoopAddSource(cf.CFRunLoopGetCurrent(), source, kCFRunLoopDefaultMode)
        cf.CFRunLoopRun()  # blocks this thread indefinitely

    t = threading.Thread(target=_run, daemon=True, name="sleep-watcher")
    t.start()
    return True
