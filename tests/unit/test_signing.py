import hashlib
import hmac

from backend.core.signing import sign_payload, verify_signature

BODY = b'{"jobId":"abc","status":"completed"}'


def test_matches_independent_hmac():
    expected = "sha256=" + hmac.new(b"k", b"1700000000." + BODY, hashlib.sha256).hexdigest()
    assert sign_payload("k", 1700000000, BODY) == expected


def test_roundtrip_verifies():
    sig = sign_payload("k", 1700000000, BODY)
    assert verify_signature("k", 1700000000, BODY, sig, now=1700000010)


def test_tampered_body_fails():
    sig = sign_payload("k", 1700000000, BODY)
    assert not verify_signature("k", 1700000000, BODY + b" ", sig, now=1700000010)


def test_wrong_secret_fails():
    sig = sign_payload("k", 1700000000, BODY)
    assert not verify_signature("other", 1700000000, BODY, sig, now=1700000010)


def test_stale_timestamp_fails():
    sig = sign_payload("k", 1700000000, BODY)
    assert not verify_signature("k", 1700000000, BODY, sig, now=1700000000 + 301)


def test_malformed_signature_fails_without_error():
    assert not verify_signature("k", 1700000000, BODY, "garbage", now=1700000010)
