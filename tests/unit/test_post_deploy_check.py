import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "post_deploy_check", Path(__file__).resolve().parents[2] / "scripts" / "post_deploy_check.py")
pdc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pdc)


def _results(api_client, api_key=None):
    def request(method, path, **kw):
        return api_client.request(method, path, **kw)
    return pdc.run_checks(request, api_key=api_key)


def test_anonymous_checks_pass_against_a_healthy_app(api_client):
    results = _results(api_client)
    # These two only hold in production (docs are on in DEBUG mode; HSTS comes from the Caddy proxy).
    production_only = {"https hsts header", "api docs are not exposed"}
    failed = [r for r in results if not r.ok and r.name not in production_only]
    assert failed == [], [(r.name, r.detail) for r in failed]
    assert any(r.name == "anonymous /analyze is rejected" and r.ok for r in results)


def test_authenticated_checks_prove_the_allowlist_is_enforced(api_client, make_client):
    reg = make_client()
    results = _results(api_client, api_key=reg.api_key)
    names = {r.name: r for r in results}
    assert names["file host allowlist is enforced"].ok, names["file host allowlist is enforced"].detail
    assert names["unknown job is 404"].ok


def test_a_wrong_api_key_is_reported_as_a_failure(api_client, make_client):
    make_client()
    results = _results(api_client, api_key="sk_claramed_wrong")
    assert any(not r.ok for r in results)


def test_unreachable_app_is_reported_not_raised():
    def request(method, path, **kw):
        raise ConnectionError("down")
    results = pdc.run_checks(request)
    assert results and all(not r.ok for r in results)
