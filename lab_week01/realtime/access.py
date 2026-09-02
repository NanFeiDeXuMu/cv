"""Access-mode planning for local, LAN, and mobile HTTPS launches."""

from __future__ import annotations

import secrets
import socket
from dataclasses import dataclass
from typing import Literal

AccessMode = Literal["local", "lan", "mobile"]


@dataclass(frozen=True)
class AccessPlan:
    """Resolved launch settings, kept independent from the Gradio UI."""

    mode: AccessMode
    server_name: str
    share: bool
    pwa: bool
    auth: tuple[str, str] | None
    notices: tuple[str, ...]


def discover_lan_ipv4_addresses() -> tuple[str, ...]:
    """Return non-loopback IPv4 candidates for same-network access."""

    addresses: set[str] = set()
    try:
        for result in socket.getaddrinfo(
            socket.gethostname(), None, family=socket.AF_INET
        ):
            address = result[4][0]
            if not address.startswith("127.") and address != "0.0.0.0":
                addresses.add(address)
    except OSError:
        return ()
    return tuple(sorted(addresses))


def create_access_plan(
    mode: AccessMode,
    *,
    port: int,
    username: str = "visiontrace",
    password: str | None = None,
    lan_addresses: tuple[str, ...] | None = None,
) -> AccessPlan:
    """Resolve safe defaults for one requested access mode."""

    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")

    if mode == "local":
        return AccessPlan(
            mode=mode,
            server_name="127.0.0.1",
            share=False,
            pwa=False,
            auth=None,
            notices=(f"Local URL: http://127.0.0.1:{port}",),
        )

    if mode == "lan":
        addresses = (
            discover_lan_ipv4_addresses()
            if lan_addresses is None
            else lan_addresses
        )
        urls = tuple(f"LAN URL: http://{address}:{port}" for address in addresses)
        if not urls:
            urls = (
                "No LAN IPv4 address was discovered; inspect the host network settings.",
            )
        return AccessPlan(
            mode=mode,
            server_name="0.0.0.0",
            share=False,
            pwa=False,
            auth=None,
            notices=urls
            + (
                "LAN HTTP can open the page, but mobile browsers may block Webcam "
                "access because the page is not HTTPS.",
            ),
        )

    if mode == "mobile":
        if not username.strip():
            raise ValueError("A non-empty username is required in mobile mode")
        resolved_password = password or secrets.token_urlsafe(12)
        if len(resolved_password) < 8:
            raise ValueError("Mobile-mode password must contain at least 8 characters")
        return AccessPlan(
            mode=mode,
            server_name="127.0.0.1",
            share=True,
            pwa=True,
            auth=(username, resolved_password),
            notices=(
                "Mobile mode creates a temporary public HTTPS tunnel.",
                f"Login username: {username}",
                f"Login password: {resolved_password}",
                "Keep the URL and credentials private; stop the process after use.",
            ),
        )

    raise ValueError(f"Unsupported access mode: {mode}")
