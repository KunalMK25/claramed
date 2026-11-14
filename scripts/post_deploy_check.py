"""Black-box checks to run right after a deploy (and again after any change).

    python scripts/post_deploy_check.py --base-url https://claramed.example.com
    CLARAMED_API_KEY=sk_claramed_... python scripts/post_deploy_check.py --base-url https://claramed.example.com

Without an API key it checks health, readiness and that anonymous access is refused. With a key it also
proves authentication, the per-client file-host allowlist and job scoping, WITHOUT analysing anything:
the test request points at a host that can never be allowed, so no file is downloaded and no job is created.
Prints PASS/FAIL per check; exits 1 if any check fails. Pass the key by environment variable, not on the
command line, so it stays out of shell history.
"""
import argparse
import os
import sys
import uuid
from dataclasses import dataclass


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


def _check(results: list, name: str, fn) -> None:
    try:
        ok, detail = fn()
    except Exception as exc:  # unreachable host, bad JSON, ... is a failed check, never a crash
        ok, detail = False, f"{type(exc).__name__}: {exc}"[:200]
    results.append(Result(name, bool(ok), detail))


def run_checks(request, api_key: str | None = None) -> list[Result]:
    """`request(method, path, **kwargs)` returns a response with status_code, json() and headers."""
    results: list[Result] = []

    def status_is(method, path, expected, **kw):
        def run():
            response = request(method, path, **kw)
            return response.status_code == expected, f"HTTP {response.status_code}"
        return run

    _check(results, "health endpoint", status_is("GET", "/api/v1/health", 200))

    def readiness():
        response = request("GET", "/api/v1/health/ready")
        body = response.json()
        return response.status_code == 200 and body.get("status") == "ready", f"status={body.get('status')}"
    _check(results, "readiness (database)", readiness)

    _check(results, "anonymous /analyze is rejected", status_is("POST", "/api/v1/analyze", 401, json={}))
    _check(results, "anonymous /analyses is rejected", status_is("GET", "/api/v1/analyses", 401))
    _check(results, "api docs are not exposed", status_is("GET", "/api/docs", 404))

    def hsts():
        value = request("GET", "/api/v1/health").headers.get("Strict-Transport-Security")
        return bool(value), value or "header missing (expected from the Caddy proxy)"
    _check(results, "https hsts header", hsts)

    if api_key:
        auth = {"Authorization": f"Bearer {api_key}"}

        _check(results, "api key is accepted", status_is("GET", "/api/v1/analyses", 200, headers=auth))

        def allowlist():
            response = request("POST", "/api/v1/analyze", headers=auth, json={
                "radiologyId": "post-deploy-check",
                "fileUrl": "https://not-allowed.example.invalid/x.png",
            })
            code = response.json().get("error", {}).get("code")
            return response.status_code == 422 and code == "host_not_allowed", f"HTTP {response.status_code} {code}"
        _check(results, "file host allowlist is enforced", allowlist)

        _check(results, "unknown job is 404",
               status_is("GET", f"/api/v1/status/{uuid.uuid4()}", 404, headers=auth))
    return results


def main() -> int:
    import requests

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True, help="e.g. https://claramed.example.com")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    session = requests.Session()

    def request(method, path, **kwargs):
        return session.request(method, base + path, timeout=20, **kwargs)

    results = run_checks(request, api_key=os.environ.get("CLARAMED_API_KEY") or None)
    width = max(len(r.name) for r in results)
    for r in results:
        print(f"{'PASS' if r.ok else 'FAIL'}  {r.name.ljust(width)}  {r.detail}")
    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
