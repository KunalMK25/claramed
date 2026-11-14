from frontend.api_client import ClaraMedAPIClient


def test_sends_bearer_key_when_configured():
    client = ClaraMedAPIClient(base_url="http://x", api_key="k")
    assert client.session.headers["Authorization"] == "Bearer k"


def test_no_authorization_header_without_a_key():
    client = ClaraMedAPIClient(base_url="http://x", api_key=None)
    assert "Authorization" not in client.session.headers
