from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """A source URL targets a non-public address — blocked as an SSRF risk."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def reject_literal_private_ip(url: str) -> None:
    """Network-free guard: reject a URL whose host is a literal private IP / localhost.

    Cheap enough to run at API-validation time (no DNS) so blatant SSRF targets
    like ``http://127.0.0.1:6379`` never reach the database. Hostnames that are
    not IP literals are left for :func:`assert_public_url` at fetch time.
    """
    host = urlparse(url).hostname
    if host is None:
        return
    if host.lower() == "localhost":
        raise UnsafeURLError("host 'localhost' is not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # not a literal IP — DNS resolution is checked at fetch time
    if _is_blocked_ip(ip):
        raise UnsafeURLError(f"url host resolves to a non-public address: {ip}")


def assert_public_url(url: str) -> None:
    """Resolve the URL host and reject if any address is non-public (SSRF guard).

    Called at fetch time — the actual point of egress — so an attacker-registered
    source can't make the worker reach internal services (Redis, cloud metadata,
    sibling containers). Resolves all A/AAAA records and blocks if ANY is private.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"unsupported url scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("url has no host")
    if host.lower() == "localhost":
        raise UnsafeURLError("host 'localhost' is not allowed")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"cannot resolve url host: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f"url host resolves to a non-public address: {ip}")
