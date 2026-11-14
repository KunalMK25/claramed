import pytest

from backend.core.security import verify_api_key
from backend.services.client_registry import register_client

URL = "https://jeevacare.test/api/webhook/claramed-callback"


def test_registers_with_hashed_key_and_secret(db):
    reg = register_client(db, name="jeevacare", webhook_url=URL,
                          allowed_file_hosts=["res.cloudinary.com"])
    assert reg.api_key.startswith("sk_claramed_")
    assert reg.client.hashed_api_key != reg.api_key
    assert verify_api_key(reg.api_key, reg.client.hashed_api_key)
    assert len(reg.webhook_secret) >= 32
    assert reg.client.scopes == ["analysis:create", "analysis:read"]
    assert reg.client.active is True


def test_hosts_are_normalised_to_lowercase(db):
    reg = register_client(db, name="x", webhook_url=URL, allowed_file_hosts=[" Res.Cloudinary.COM "])
    assert reg.client.allowed_file_hosts == ["res.cloudinary.com"]


def test_wildcard_host_is_accepted(db):
    reg = register_client(db, name="x", webhook_url=URL, allowed_file_hosts=["*.cloudinary.com"])
    assert reg.client.allowed_file_hosts == ["*.cloudinary.com"]


def test_optional_callback_token_is_stored(db):
    reg = register_client(db, name="x", webhook_url=URL, allowed_file_hosts=["a.test"],
                          callback_auth_token="jv-token")
    assert reg.client.callback_auth_token == "jv-token"


def test_rejects_non_https_webhook(db):
    with pytest.raises(ValueError, match="https"):
        register_client(db, name="x", webhook_url="http://insecure.test/cb",
                        allowed_file_hosts=["a.test"])


def test_rejects_empty_host_allowlist(db):
    with pytest.raises(ValueError, match="allowed_file_hosts"):
        register_client(db, name="x", webhook_url=URL, allowed_file_hosts=[])


@pytest.mark.parametrize("bad", ["https://res.cloudinary.com/x", "res.cloudinary.com/x", "localhost",
                                 "*", "*.", "10.0.0.1:8080"])
def test_rejects_host_that_is_not_a_bare_hostname(db, bad):
    with pytest.raises(ValueError, match="hostname"):
        register_client(db, name="x", webhook_url=URL, allowed_file_hosts=[bad])


def test_duplicate_name_rejected(db):
    register_client(db, name="dup", webhook_url=URL, allowed_file_hosts=["a.test"])
    with pytest.raises(ValueError, match="already exists"):
        register_client(db, name="dup", webhook_url=URL, allowed_file_hosts=["a.test"])
