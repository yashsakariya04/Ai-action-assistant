"""
core/url_safety.py — SSRF protection helper.

Blocks requests to private/link-local IP ranges before any HTTP call
is made with a user-supplied URL.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import config

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),  # AWS/Azure metadata service
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def assert_safe_url(url: str) -> None:
    """
    Raise ValueError if the URL resolves to a private/internal IP address
    or uses a disallowed scheme.

    Call this before any requests.get(url, ...) with user-supplied URLs.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()

    if config.IS_PRODUCTION:
        if scheme != "https":
            raise ValueError(
                f"URL scheme '{scheme}' is not allowed in production. Use https://."
            )
    else:
        if scheme not in ("http", "https"):
            raise ValueError(f"URL scheme '{scheme}' is not allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"URL '{url}' has no resolvable hostname.")

    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except (socket.gaierror, ValueError) as exc:
        raise ValueError(f"Could not resolve hostname '{hostname}': {exc}") from exc

    for network in _BLOCKED_NETWORKS:
        if ip in network:
            raise ValueError(
                f"URL '{url}' resolves to a blocked private address ({ip})."
            )
