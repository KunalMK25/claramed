"""Download a client-supplied file URL safely (SSRF-hardened).

Controls: https only, plain URL (no userinfo, default port), host must be in the client's allowlist,
every resolved address must be public, redirects are re-validated hop by hop, size is capped while
streaming, there is one overall deadline, and the content is checked by magic bytes (not headers).

Known limit: DNS is resolved and checked, then httpx connects by hostname, so a DNS-rebinding window
remains. The per-client host allowlist is the primary control.
"""
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx


class FetchError(Exception):
    """A client-fixable intake problem. `code` is part of the public API contract."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class FetchedFile:
    content: bytes
    kind_detected: str  # "png" | "jpeg" | "pdf"
    extension: str


_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "png", ".png"),
    (b"\xff\xd8\xff", "jpeg", ".jpg"),
    (b"%PDF-", "pdf", ".pdf"),
]
_ALLOWED = {"radiology": {"png", "jpeg"}, "document": {"pdf"}}
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def host_allowed(host: str, allowed: list[str]) -> bool:
    """Exact match, or '*.example.com' for any subdomain (not the bare domain)."""
    host = host.lower()
    for pattern in allowed:
        pattern = pattern.lower()
        if pattern.startswith("*."):
            if host.endswith(pattern[1:]) and host != pattern[2:]:
                return True
        elif host == pattern:
            return True
    return False


def default_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError("fetch_failed", f"cannot resolve host: {exc.__class__.__name__}") from exc
    return [info[4][0] for info in infos]


def _is_public(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


def _validate(url: str, allowed_hosts: list[str], resolver) -> None:
    try:
        parsed = urlparse(url)
        host, port = parsed.hostname, parsed.port
    except ValueError as exc:
        raise FetchError("invalid_url", "URL is not valid") from exc
    if parsed.scheme != "https":
        raise FetchError("invalid_scheme", "only https URLs are accepted")
    if not host or parsed.username or parsed.password or port not in (None, 443):
        raise FetchError("invalid_url", "URL must be a plain https URL on the default port")
    if not host_allowed(host, allowed_hosts):
        raise FetchError("host_not_allowed", "host is not in the client's allowlist")
    addresses = resolver(host)
    if not addresses or not all(_is_public(a) for a in addresses):
        raise FetchError("blocked_address", "host resolves to a non-public address")


def _detect(content: bytes, kind: str) -> tuple[str, str]:
    for magic, name, ext in _MAGIC:
        if content.startswith(magic):
            if name in _ALLOWED[kind]:
                return name, ext
            break
    raise FetchError("bad_content", f"file content is not a valid {kind} file")


def fetch_file(
    url: str,
    *,
    allowed_hosts: list[str],
    kind: str,
    max_bytes: int,
    client: httpx.Client | None = None,
    resolver=None,
    max_redirects: int = 3,
    total_timeout: float = 30.0,
) -> FetchedFile:
    """Download `url` and return its bytes if it passes every check; raise FetchError otherwise."""
    if kind not in _ALLOWED:
        raise ValueError(f"unknown kind: {kind}")
    resolver = resolver or default_resolver
    deadline = time.monotonic() + total_timeout

    def check_deadline():
        if time.monotonic() > deadline:
            raise FetchError("fetch_failed", "download timed out")

    owns_client = client is None
    client = client or httpx.Client(timeout=_TIMEOUT, follow_redirects=False)
    try:
        current = url
        for _hop in range(max_redirects + 1):
            check_deadline()
            _validate(current, allowed_hosts, resolver)
            redirect_to = None
            buffer = bytearray()
            try:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        redirect_to = response.headers.get("location")
                        if not redirect_to:
                            raise FetchError("fetch_failed", "redirect without a location")
                    else:
                        if response.status_code != 200:
                            raise FetchError("fetch_failed", f"upstream returned {response.status_code}")
                        declared = response.headers.get("content-length")
                        if declared and declared.isdigit() and int(declared) > max_bytes:
                            raise FetchError("too_large", "file exceeds the size limit")
                        for chunk in response.iter_bytes():
                            buffer.extend(chunk)
                            if len(buffer) > max_bytes:
                                raise FetchError("too_large", "file exceeds the size limit")
                            check_deadline()
            except httpx.HTTPError as exc:
                raise FetchError("fetch_failed", f"download failed: {type(exc).__name__}") from exc
            if redirect_to is not None:
                current = urljoin(current, redirect_to)
                continue
            name, ext = _detect(bytes(buffer), kind)
            return FetchedFile(content=bytes(buffer), kind_detected=name, extension=ext)
        raise FetchError("redirect_limit", "too many redirects")
    finally:
        if owns_client:
            client.close()
