def test_db_is_the_test_database(db):
    assert db.bind.url.database == "claramed_test"


def test_api_client_reaches_health(api_client):
    assert api_client.get("/api/v1/health").status_code == 200


def test_storage_dir_is_isolated(storage_dir):
    assert "claramed_storage" in str(storage_dir)
