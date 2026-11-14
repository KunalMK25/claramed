"""Test double for JeevaCare's callback route. Verifies the ClaraMed signature (and optional token)."""
import json

import httpx

from backend.core.signing import verify_signature


class JeevaCareStub:
    def __init__(self, secret: str, expected_token: str | None = None):
        self.secret = secret
        self.expected_token = expected_token
        self.received: list[dict] = []
        self.headers_seen: list[dict] = []
        self.fail_next = 0            # that many requests answer 500 first
        self.requests = 0

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        self.headers_seen.append(dict(request.headers))
        if self.fail_next > 0:
            self.fail_next -= 1
            return httpx.Response(500, json={"success": False})
        if self.expected_token is not None and request.headers.get("Authorization") != f"Bearer {self.expected_token}":
            return httpx.Response(401, json={"success": False, "reason": "bad token"})
        ts = request.headers.get("X-ClaraMed-Timestamp", "0")
        sig = request.headers.get("X-ClaraMed-Signature", "")
        if not verify_signature(self.secret, int(ts), request.content, sig):
            return httpx.Response(401, json={"success": False, "reason": "bad signature"})
        self.received.append(json.loads(request.content))
        return httpx.Response(200, json={"success": True})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._handle), follow_redirects=False)
