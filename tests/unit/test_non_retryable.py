"""Bad input fails fast with a failed callback; transient errors keep their retries."""
import pytest

from backend.models.analysis import AnalysisStatus
from backend.models.document import DocumentType
from backend.services.document_service import DocumentService
from backend.services.radiology_service import RadiologyService
from backend.workers import callbacks
from backend.workers.tasks import process_document_async, process_radiology_async
from tests.support.factories import make_analysis
from tests.support.jeevacare_stub import JeevaCareStub


@pytest.fixture
def stub(make_client, monkeypatch):
    reg = make_client()
    s = JeevaCareStub(reg.webhook_secret)
    monkeypatch.setattr(callbacks, "_http_client", s.client)
    return reg, s


def _counting(monkeypatch, cls, name):
    calls = []
    original = getattr(cls, name)

    def wrapper(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(cls, name, wrapper)
    return calls


def test_corrupt_image_fails_once_and_sends_a_failed_callback(db, stub, storage_dir, monkeypatch):
    reg, s = stub
    a, _ = make_analysis(db, reg.client, status=AnalysisStatus.PENDING, file_in=storage_dir)   # 4-byte "PNG"
    calls = _counting(monkeypatch, RadiologyService, "analyze_chest_xray")
    process_radiology_async.apply(args=[str(a.id), str(a.documents[0].id)])
    db.expire_all()
    assert len(calls) == 1
    assert db.get(type(a), a.id).status == AnalysisStatus.FAILED
    assert s.received[-1]["status"] == "failed" and s.received[-1]["error"] == {"code": "analysis_failed"}


def test_corrupt_pdf_fails_once_and_sends_a_failed_callback(db, stub, storage_dir, monkeypatch):
    reg, s = stub
    a, _ = make_analysis(db, reg.client, record="doc-1", kind="document", status=AnalysisStatus.PENDING,
                         file_in=storage_dir, content=b"%PDF-1.4\nnot really a pdf", filename="r.pdf",
                         file_type=DocumentType.PDF)
    calls = _counting(monkeypatch, DocumentService, "extract_text_from_pdf")
    process_document_async.apply(args=[str(a.id), str(a.documents[0].id)])
    db.expire_all()
    assert len(calls) == 1
    assert db.get(type(a), a.id).status == AnalysisStatus.FAILED
    assert s.received[-1]["status"] == "failed" and s.received[-1]["documentId"] == "doc-1"


def test_transient_error_is_still_retried(db, stub, storage_dir, monkeypatch):
    reg, s = stub
    a, _ = make_analysis(db, reg.client, status=AnalysisStatus.PENDING, file_in=storage_dir)
    calls = []

    def flaky(self, path):
        calls.append(1)
        raise RuntimeError("temporary glitch")

    monkeypatch.setattr(RadiologyService, "analyze_chest_xray", flaky)
    process_radiology_async.apply(args=[str(a.id), str(a.documents[0].id)])
    assert len(calls) > 1                                   # retried before giving up
    db.expire_all()
    assert db.get(type(a), a.id).status == AnalysisStatus.FAILED
