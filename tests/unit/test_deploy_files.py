"""Static checks on the production deployment files (docker-compose.prod.yml, Dockerfile, Caddyfile, env template).

Docker itself is not available in CI here, so these tests pin the properties that have gone wrong before.
"""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _text(path):
    return (ROOT / path).read_text()


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(_text("docker-compose.prod.yml"))


LONG_RUNNING = ["postgres", "redis", "api", "worker", "beat", "caddy"]


def test_expected_services_exist(compose):
    assert set(LONG_RUNNING + ["migrate"]) <= set(compose["services"])


def test_only_caddy_is_published_to_the_world(compose):
    for name, svc in compose["services"].items():
        ports = [str(p) for p in svc.get("ports", [])]
        if name == "caddy":
            assert any(p.startswith("80:") for p in ports) and any(p.startswith("443:") for p in ports)
        elif name == "ui":
            assert all(p.startswith("127.0.0.1:") for p in ports), "UI must bind to localhost only"
        else:
            assert not ports, f"{name} must not publish ports"


def test_long_running_services_restart_and_cap_their_logs(compose):
    for name in LONG_RUNNING:
        svc = compose["services"][name]
        assert svc["restart"] == "unless-stopped", name
        assert svc["logging"]["options"]["max-size"], f"{name} needs a log size cap"
    assert compose["services"]["migrate"]["restart"] == "no"


def test_core_services_have_healthchecks(compose):
    for name in ("postgres", "redis", "api", "worker"):
        assert "healthcheck" in compose["services"][name], name


def test_api_and_worker_share_the_same_storage_volume(compose):
    def storage_mount(name):
        return [v for v in compose["services"][name]["volumes"] if v.endswith(":/app/storage")]
    assert storage_mount("api") and storage_mount("api") == storage_mount("worker")
    assert storage_mount("api")[0].split(":")[0] in compose["volumes"]      # a named volume, not a host path


def test_migrations_run_once_before_the_apps_start(compose):
    assert "alembic upgrade head" in " ".join(compose["services"]["migrate"]["command"])
    for name in ("api", "worker", "beat"):
        assert compose["services"][name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"


def test_no_literal_credentials_in_the_compose_file():
    text = _text("docker-compose.prod.yml")
    assert "claramed_dev_password" not in text
    assert "${POSTGRES_PASSWORD:?" in text and "${CLARAMED_DOMAIN:?" in text      # required, no silent default


def test_production_mode_is_forced(compose):
    env = compose["services"]["api"]["environment"]
    assert env["APP_ENV"] == "production" and str(env["DEBUG"]).lower() == "false"
    assert env["STORAGE_SHARED_CONFIRMED"] in (True, "true")


def test_data_is_on_named_volumes(compose):
    assert {"pgdata", "redisdata", "storage", "caddy_data"} <= set(compose["volumes"])


def test_dockerfile_is_non_root_cpu_torch_and_bakes_the_model():
    d = _text("Dockerfile")
    assert re.search(r"^USER app\s*$", d, re.M)
    assert "download.pytorch.org/whl/cpu" in d
    assert "libgl1-mesa-glx" not in d                                           # removed from current Debian
    assert "densenet121-res224-all" in d                                        # weights baked into the image
    assert re.search(r"^FROM python:3\.11-slim-bookworm", d, re.M)              # pinned base, not a moving tag
    assert "alembic upgrade head" not in d.split("CMD")[-1]                     # migrations are the migrate service's job


def test_dockerignore_keeps_migrations_and_excludes_secrets():
    ignore = [l.strip() for l in _text(".dockerignore").splitlines() if l.strip() and not l.startswith("#")]
    assert "migrations/versions/" not in ignore, "alembic needs the revision files inside the image"
    for must_exclude in (".env", "venv/", "storage/", ".git/"):
        assert must_exclude in ignore, must_exclude


def test_caddyfile_terminates_tls_and_proxies_to_the_api():
    c = _text("deploy/Caddyfile")
    assert "{$CLARAMED_DOMAIN}" in c and "reverse_proxy api:8000" in c
    assert "Strict-Transport-Security" in c and "request_body" in c


def test_env_template_lists_required_settings_without_real_secrets():
    values = dict(
        line.split("=", 1) for line in _text(".env.production.example").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    for key in ("CLARAMED_DOMAIN", "POSTGRES_PASSWORD", "API_KEY_HASH_SECRET", "SECRET_KEY", "GROQ_API_KEY",
                "WORKER_CONCURRENCY"):
        assert key in values, key
    for key in ("POSTGRES_PASSWORD", "API_KEY_HASH_SECRET", "SECRET_KEY", "GROQ_API_KEY"):
        assert values[key].strip() in ("", "CHANGE_ME"), f"{key} must be a placeholder"


def test_backup_script_dumps_the_database_and_prunes_old_files():
    s = _text("scripts/backup.sh")
    assert s.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in s
    assert "pg_dump" in s and "find " in s and "-mtime" in s
