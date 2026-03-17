"""CA certificate generation and macOS System Keychain management."""
from __future__ import annotations

import subprocess
from pathlib import Path

CONFDIR = Path.home() / ".config" / "agentic-store" / "mitmproxy"
CA_CERT_PEM = CONFDIR / "mitmproxy-ca-cert.pem"
CA_BUNDLE_PEM = CONFDIR / "mitmproxy-ca.pem"


def ensure_ca_generated() -> Path:
    """Generate the mitmproxy CA cert by running mitmproxy briefly if not present."""
    CONFDIR.mkdir(parents=True, exist_ok=True)
    if CA_CERT_PEM.exists():
        return CA_CERT_PEM

    # Use mitmproxy's cert store to generate CA
    from mitmproxy.certs import CertStore
    store = CertStore.from_store(CONFDIR, "mitmproxy", 2048)  # noqa: F841 — side effect generates files
    return CA_CERT_PEM


def install_ca_to_keychain() -> None:
    """Install and trust our CA cert in the user login keychain.

    No admin password required. User-level trust is sufficient for Chromium-based
    browsers (Brave, Chrome, Cursor) and other user-space apps. macOS Ventura+
    blocks system-keychain trust settings from non-interactive shells even as root,
    so we rely on the login keychain only.
    """
    cert_path = ensure_ca_generated()
    result = subprocess.run(
        ["security", "add-trusted-cert", "-r", "trustRoot", str(cert_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Keychain install failed: {result.stderr.strip()}")


def remove_ca_from_keychain() -> None:
    """Remove our CA cert from the user login keychain trust store."""
    if CA_CERT_PEM.exists():
        subprocess.run(
            ["security", "remove-trusted-cert", str(CA_CERT_PEM)],
            capture_output=True, text=True,
        )


def is_ca_installed() -> bool:
    """Check whether our CA cert is actually trusted (not just present in keychain)."""
    if not CA_CERT_PEM.exists():
        return False
    result = subprocess.run(
        ["security", "verify-cert", "-c", str(CA_CERT_PEM)],
        capture_output=True, text=True,
    )
    return result.returncode == 0
