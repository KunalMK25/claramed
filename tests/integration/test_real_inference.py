"""Real TorchXRayVision inference through the whole flow. Slow (model load): run with -m slow."""
import io

import pytest
from PIL import Image

from backend.services import integration_service
from backend.services.url_fetcher import FetchedFile
from backend.workers import callbacks
from tests.support.jeevacare_stub import JeevaCareStub


@pytest.mark.slow
def test_real_xray_inference_reaches_the_callback(monkeypatch, make_client, auth_headers, api_client):
    reg = make_client()
    stub = JeevaCareStub(reg.webhook_secret)
    monkeypatch.setattr(callbacks, "_http_client", stub.client)
    buf = io.BytesIO()
    Image.effect_noise((512, 512), 40).convert("L").save(buf, "PNG")
    monkeypatch.setattr(integration_service, "fetch_file", lambda url, **kw: FetchedFile(
        content=buf.getvalue(), kind_detected="png", extension=".png"))
    r = api_client.post("/api/v1/analyze", headers=auth_headers(reg.api_key), json={
        "radiologyId": "real-1", "imageUrl": "https://res.cloudinary.com/x/a.png"})
    assert r.status_code == 202
    cb = stub.received[0]
    assert cb["status"] == "completed"
    assert len(cb["results"]["findings"]) == 18
    assert all(0.0 <= f["score"] <= 1.0 for f in cb["results"]["findings"])
