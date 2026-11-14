"""HMAC signing for outbound webhook callbacks."""
import hashlib
import hmac
import time

SIGNATURE_PREFIX = "sha256="
DEFAULT_TOLERANCE_SECONDS = 300


def sign_payload(secret: str, timestamp: int, body: bytes) -> str:
    """Return 'sha256=<hex>' over '<timestamp>.<body>'."""
    message = f"{int(timestamp)}.".encode() + body
    return SIGNATURE_PREFIX + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str,
    timestamp: int,
    body: bytes,
    signature: str,
    now: float | None = None,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
) -> bool:
    """Constant-time check; rejects stale timestamps and malformed signatures."""
    current = time.time() if now is None else now
    if abs(current - int(timestamp)) > tolerance:
        return False
    expected = sign_payload(secret, int(timestamp), body)
    return hmac.compare_digest(expected.encode(), signature.encode())
