"""macOS system-level HTTPS proxy configuration via networksetup."""
from __future__ import annotations

import ctypes
import ctypes.util
import subprocess
import threading
from typing import Callable


def _get_network_services() -> list[str]:
    result = subprocess.run(
        ["networksetup", "-listallnetworkservices"],
        capture_output=True, text=True
    )
    services = []
    for line in result.stdout.splitlines():
        line = line.strip()
        # Skip empty lines, disabled services (*), and the header/disclaimer sentence
        if not line or line.startswith("*") or "network service" in line.lower():
            continue
        services.append(line)
    return services


def set_system_proxy(port: int = 8766) -> list[str]:
    """Configure macOS system HTTPS + HTTP proxy on all active network services."""
    services = _get_network_services()
    configured = []
    for svc in services:
        subprocess.run(["networksetup", "-setwebproxy", svc, "127.0.0.1", str(port)], capture_output=True)
        subprocess.run(["networksetup", "-setsecurewebproxy", svc, "127.0.0.1", str(port)], capture_output=True)
        subprocess.run(["networksetup", "-setwebproxystate", svc, "on"], capture_output=True)
        subprocess.run(["networksetup", "-setsecurewebproxystate", svc, "on"], capture_output=True)
        configured.append(svc)
    return configured


def remove_system_proxy() -> None:
    """Disable system proxy on all network services."""
    for svc in _get_network_services():
        subprocess.run(["networksetup", "-setwebproxystate", svc, "off"], capture_output=True)
        subprocess.run(["networksetup", "-setsecurewebproxystate", svc, "off"], capture_output=True)


def is_system_proxy_set(port: int = 8766) -> bool:
    """Check if macOS system proxy is pointing to our port."""
    services = _get_network_services()
    if not services:
        return False
    result = subprocess.run(
        ["networksetup", "-getsecurewebproxy", services[0]],
        capture_output=True, text=True
    )
    return "127.0.0.1" in result.stdout and str(port) in result.stdout and "Yes" in result.stdout


# Module-level ref so the C callback is never garbage-collected.
_sleep_wake_cb_ref: object = None

_kIOMessageSystemWillSleep = 0xe0000280
_kIOMessageSystemHasPoweredOn = 0xe0000300


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
        cf.CFRunLoopAddSource.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        cf.CFRunLoopRun.argtypes = []

        # kCFRunLoopDefaultMode is a CFStringRef global — read its pointer value.
        kCFRunLoopDefaultMode = ctypes.c_void_p.in_dll(cf, "kCFRunLoopDefaultMode").value
    except Exception:
        return False

    # Mutable state shared between the thread and the callback closure.
    _state: dict[str, int] = {"root_port": 0}

    _IOServiceInterestCallback = ctypes.CFUNCTYPE(
        None,
        ctypes.c_void_p,   # refcon
        ctypes.c_uint32,   # io_service_t (root port back-channel)
        ctypes.c_uint32,   # messageType
        ctypes.c_void_p,   # messageArgument (notification ID for IOAllowPowerChange)
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
