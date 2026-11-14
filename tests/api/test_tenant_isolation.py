"""Client B must not reach client A's analyses through the original /analyses routes."""
import pytest

from backend.models.analysis import AnalysisStatus, AnalysisType, MedicalAnalysis


@pytest.fixture
def two_clients(make_client, auth_headers):
    a, b = make_client("a"), make_client("b")
    return a, b, auth_headers(a.api_key), auth_headers(b.api_key)


def _analysis(db, client_id=None):
    row = MedicalAnalysis(analysis_type=AnalysisType.SYMPTOM, status=AnalysisStatus.COMPLETED,
                          requesting_client_id=client_id)
    db.add(row)
    db.commit()
    return str(row.id)


def test_owner_can_read_own_analysis(api_client, two_clients, db):
    a, _, ha, _ = two_clients
    aid = _analysis(db, a.client.id)
    assert api_client.get(f"/api/v1/analyses/{aid}", headers=ha).status_code == 200


def test_other_client_cannot_read_detail_or_results(api_client, two_clients, db):
    a, _, _, hb = two_clients
    aid = _analysis(db, a.client.id)
    assert api_client.get(f"/api/v1/analyses/{aid}", headers=hb).status_code == 403
    assert api_client.get(f"/api/v1/analyses/{aid}/results", headers=hb).status_code == 403


def test_other_client_cannot_upload_to_it(api_client, two_clients, db):
    a, _, _, hb = two_clients
    aid = _analysis(db, a.client.id)
    pdf = {"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}
    png = {"file": ("a.png", b"\x89PNG", "image/png")}
    assert api_client.post(f"/api/v1/analyses/{aid}/documents", files=pdf, headers=hb).status_code == 403
    assert api_client.post(f"/api/v1/analyses/{aid}/images", files=png, headers=hb).status_code == 403


def test_list_only_shows_own_analyses(api_client, two_clients, db):
    a, b, ha, hb = two_clients
    mine, theirs = _analysis(db, a.client.id), _analysis(db, b.client.id)
    ids = {item["analysis_id"] for item in api_client.get("/api/v1/analyses", headers=ha).json()["analyses"]}
    assert mine in ids and theirs not in ids


def test_ownerless_legacy_analysis_is_denied_to_everyone(api_client, two_clients, db):
    _, _, ha, hb = two_clients
    aid = _analysis(db, None)
    assert api_client.get(f"/api/v1/analyses/{aid}", headers=ha).status_code == 403
    assert api_client.get(f"/api/v1/analyses/{aid}", headers=hb).status_code == 403
