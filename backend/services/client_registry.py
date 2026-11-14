"""Register integration clients (admin operation)."""
import re
import secrets
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.security import generate_api_key, hash_api_key
from backend.models.integration_client import IntegrationClient

DEFAULT_SCOPES = ["analysis:create", "analysis:read"]
# A bare DNS name with at least one dot, optionally prefixed by "*." (subdomains only).
_HOST_RE = re.compile(r"^(\*\.)?([a-z0-9-]+\.)+[a-z0-9-]+$")


@dataclass
class RegisteredClient:
    client: IntegrationClient
    api_key: str
    webhook_secret: str


def _validate(webhook_url: str, hosts: list[str]) -> list[str]:
    parsed = urlparse(webhook_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("webhook_url must be an https URL")
    if not hosts:
        raise ValueError("allowed_file_hosts must contain at least one hostname")
    cleaned = [h.strip().lower() for h in hosts]
    for host in cleaned:
        if not _HOST_RE.match(host):
            raise ValueError(f"allowed_file_hosts entry is not a bare hostname: {host!r}")
    return cleaned


def register_client(
    db: Session,
    *,
    name: str,
    webhook_url: str,
    allowed_file_hosts: list[str],
    scopes: list[str] | None = None,
    description: str | None = None,
    callback_auth_token: str | None = None,
) -> RegisteredClient:
    """Create a client. The API key and webhook secret are returned once and not recoverable."""
    hosts = _validate(webhook_url, allowed_file_hosts)
    api_key = generate_api_key()
    webhook_secret = secrets.token_hex(32)
    client = IntegrationClient(
        client_name=name,
        description=description,
        hashed_api_key=hash_api_key(api_key),
        scopes=list(scopes or DEFAULT_SCOPES),
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
        callback_auth_token=callback_auth_token,
        allowed_file_hosts=hosts,
        active=True,
    )
    db.add(client)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"client {name!r} already exists") from exc
    return RegisteredClient(client=client, api_key=api_key, webhook_secret=webhook_secret)
