from backend.core.config import production_config_errors, storage_topology_warning

GOOD = dict(app_env="production", debug=False, api_key_hash_secret="a" * 48, secret_key="b" * 48)


def test_a_correct_production_config_has_no_errors():
    assert production_config_errors(**GOOD) == []


def test_default_secrets_are_rejected_in_production():
    errs = production_config_errors(**{**GOOD, "api_key_hash_secret": "change_this_to_a_secure_random_string"})
    assert any("API_KEY_HASH_SECRET" in e for e in errs)
    errs = production_config_errors(**{**GOOD, "secret_key": "change_this_to_a_secure_random_string_for_jwt"})
    assert any("SECRET_KEY" in e for e in errs)


def test_short_secrets_are_rejected():
    assert production_config_errors(**{**GOOD, "secret_key": "short"})


def test_debug_is_rejected_in_production():
    assert any("DEBUG" in e for e in production_config_errors(**{**GOOD, "debug": True}))


def test_development_is_never_blocked():
    assert production_config_errors(app_env="development", debug=True, api_key_hash_secret="x", secret_key="y") == []


def test_topology_warning_can_be_confirmed_away():
    assert storage_topology_warning("production", "local") is not None
    assert storage_topology_warning("production", "local", shared_volume_confirmed=True) is None
