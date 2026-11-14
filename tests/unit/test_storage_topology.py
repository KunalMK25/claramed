from backend.core.config import storage_topology_warning


def test_production_with_local_storage_warns():
    msg = storage_topology_warning("production", "local")
    assert msg and "worker" in msg and "s3" in msg.lower()


def test_other_combinations_do_not_warn():
    assert storage_topology_warning("development", "local") is None
    assert storage_topology_warning("production", "s3") is None
    assert storage_topology_warning("staging", "local") is None
