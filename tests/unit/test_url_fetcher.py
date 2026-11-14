import time

import httpx
import pytest

from backend.services.url_fetcher import FetchError, fetch_file

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64


def PUBLIC(host):
    return ["93.184.216.34"]


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def _ok(content, ctype="image/png"):
    return lambda req: httpx.Response(200, content=content, headers={"content-type": ctype})


def fetch(url="https://res.cloudinary.com/a/x.png", handler=None, kind="radiology",
          hosts=("res.cloudinary.com",), max_bytes=1024, resolver=PUBLIC, **kw):
    return fetch_file(url, allowed_hosts=list(hosts), kind=kind, max_bytes=max_bytes,
                      client=_client(handler or _ok(PNG)), resolver=resolver, **kw)


def test_downloads_png():
    f = fetch()
    assert f.content == PNG and f.kind_detected == "png" and f.extension == ".png"


def test_downloads_jpeg_and_pdf():
    assert fetch(handler=_ok(JPEG)).kind_detected == "jpeg"
    assert fetch("https://res.cloudinary.com/a/r.pdf", _ok(PDF), kind="document").kind_detected == "pdf"


@pytest.mark.parametrize("url,code", [
    ("http://res.cloudinary.com/a.png", "invalid_scheme"),
    ("https://user:pw@res.cloudinary.com/a.png", "invalid_url"),
    ("https://res.cloudinary.com:8443/a.png", "invalid_url"),
    ("https://evil.example/a.png", "host_not_allowed"),
    ("not a url", "invalid_scheme"),
])
def test_rejects_bad_urls_without_any_request(url, code):
    def boom(req):
        raise AssertionError("no request should be made")
    with pytest.raises(FetchError) as e:
        fetch(url, handler=boom)
    assert e.value.code == code


def test_wildcard_host_matches_subdomain_only():
    fetch("https://a.cdn.test/x.png", hosts=("*.cdn.test",))
    with pytest.raises(FetchError) as e:
        fetch("https://cdn.test/x.png", hosts=("*.cdn.test",))
    assert e.value.code == "host_not_allowed"


@pytest.mark.parametrize("ip", ["10.0.0.5", "127.0.0.1", "169.254.169.254", "::1", "192.168.1.9",
                                "::ffff:127.0.0.1", "100.64.0.1"])
def test_blocks_non_public_addresses(ip):
    with pytest.raises(FetchError) as e:
        fetch(resolver=lambda h: [ip])
    assert e.value.code == "blocked_address"


def test_blocks_when_any_resolved_address_is_private():
    with pytest.raises(FetchError) as e:
        fetch(resolver=lambda h: ["93.184.216.34", "10.0.0.5"])
    assert e.value.code == "blocked_address"


def test_blocks_when_nothing_resolves():
    with pytest.raises(FetchError) as e:
        fetch(resolver=lambda h: [])
    assert e.value.code == "blocked_address"


def test_follows_redirect_to_allowed_host():
    def handler(req):
        if req.url.path == "/a.png":
            return httpx.Response(302, headers={"location": "https://res.cloudinary.com/b.png"})
        return httpx.Response(200, content=PNG)
    assert fetch(handler=handler).content == PNG


def test_rejects_redirect_to_disallowed_host():
    def handler(req):
        return httpx.Response(302, headers={"location": "https://evil.example/x.png"})
    with pytest.raises(FetchError) as e:
        fetch(handler=handler)
    assert e.value.code == "host_not_allowed"


def test_rejects_redirect_to_plain_http():
    def handler(req):
        return httpx.Response(302, headers={"location": "http://res.cloudinary.com/x.png"})
    with pytest.raises(FetchError) as e:
        fetch(handler=handler)
    assert e.value.code == "invalid_scheme"


def test_redirect_loop_is_limited():
    def handler(req):
        return httpx.Response(302, headers={"location": "https://res.cloudinary.com/a.png"})
    with pytest.raises(FetchError) as e:
        fetch(handler=handler)
    assert e.value.code == "redirect_limit"


def test_rejects_oversize_by_header_and_by_stream():
    big = b"\x89PNG\r\n\x1a\n" + b"0" * 5000
    with pytest.raises(FetchError) as e:
        fetch(handler=_ok(big), max_bytes=1024)
    assert e.value.code == "too_large"

    def chunked(req):
        return httpx.Response(200, stream=httpx.ByteStream(big))
    with pytest.raises(FetchError) as e2:
        fetch(handler=chunked, max_bytes=1024)
    assert e2.value.code == "too_large"


def test_rejects_content_that_is_not_the_claimed_kind():
    with pytest.raises(FetchError) as e:
        fetch(handler=_ok(b"<html>nope</html>", "image/png"))
    assert e.value.code == "bad_content"
    with pytest.raises(FetchError) as e2:
        fetch("https://res.cloudinary.com/a.pdf", _ok(PNG), kind="document")
    assert e2.value.code == "bad_content"
    with pytest.raises(FetchError) as e3:
        fetch(handler=_ok(PDF), kind="radiology")
    assert e3.value.code == "bad_content"


def test_non_200_is_fetch_failed():
    with pytest.raises(FetchError) as e:
        fetch(handler=lambda r: httpx.Response(403))
    assert e.value.code == "fetch_failed"


def test_transport_error_is_fetch_failed():
    def boom(req):
        raise httpx.ConnectError("down")
    with pytest.raises(FetchError) as e:
        fetch(handler=boom)
    assert e.value.code == "fetch_failed"


def test_slow_drip_hits_the_total_deadline():
    class Slow(httpx.SyncByteStream):
        def __iter__(self):
            yield b"\x89PNG\r\n\x1a\n"
            for _ in range(50):
                time.sleep(0.03)
                yield b"x" * 10

    with pytest.raises(FetchError) as e:
        fetch(handler=lambda req: httpx.Response(200, stream=Slow()), max_bytes=10_000, total_timeout=0.1)
    assert e.value.code == "fetch_failed"


def test_unknown_kind_is_a_programming_error():
    with pytest.raises(ValueError):
        fetch(kind="symptom")
