"""Static checks on the native (no Docker) deployment: systemd units, Caddyfile, env template, helper scripts,
and docs/DEPLOYMENT_NATIVE.md. The units cannot be run here (no systemd), so these pin the properties that matter."""
import configparser
import re
from pathlib import Path

import pytest

from backend.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "deploy" / "native"
SERVICES = ["claramed-migrate", "claramed-api", "claramed-worker", "claramed-beat"]
EXTRA_ENV_KEYS = {"WORKER_CONCURRENCY"}          # read by the systemd unit, not by the app


def _unit(name):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read(NATIVE / f"{name}.service")
    return parser


@pytest.mark.parametrize("name", SERVICES)
def test_unit_runs_unprivileged_with_the_shared_env_file(name):
    s = _unit(name)["Service"]
    assert s["User"] == "claramed" and s["Group"] == "claramed"
    assert s["EnvironmentFile"] == "/etc/claramed/claramed.env"
    assert s["WorkingDirectory"] == "/opt/claramed/app"
    assert s["ExecStart"].startswith("/opt/claramed/venv/bin/")
    for hardening in ("NoNewPrivileges", "PrivateTmp", "ProtectHome"):
        assert s[hardening] == "true", hardening
    assert s["ProtectSystem"] == "strict" and "/var/lib/claramed" in s["ReadWritePaths"]


@pytest.mark.parametrize("name", ["claramed-api", "claramed-worker", "claramed-beat"])
def test_long_running_units_restart_and_wait_for_migrations(name):
    u = _unit(name)
    assert u["Service"]["Restart"] == "always"
    assert "claramed-migrate.service" in u["Unit"]["Requires"]
    assert "claramed-migrate.service" in u["Unit"]["After"]
    assert "postgresql.service" in u["Unit"]["Requires"] and "redis-server.service" in u["Unit"]["Requires"]
    assert u["Install"]["WantedBy"] == "multi-user.target"


def test_migrate_is_a_remain_after_exit_oneshot_running_alembic():
    s = _unit("claramed-migrate")["Service"]
    assert s["Type"] == "oneshot" and s["RemainAfterExit"] == "yes"
    assert s["ExecStart"].endswith("alembic upgrade head")


def test_api_listens_on_loopback_only_behind_caddy():
    s = _unit("claramed-api")["Service"]["ExecStart"]
    assert "--host 127.0.0.1" in s and "0.0.0.0" not in s
    assert "--proxy-headers" in s and "--forwarded-allow-ips 127.0.0.1" in s


def test_worker_is_memory_capped_and_gets_time_to_finish_jobs():
    s = _unit("claramed-worker")["Service"]
    assert "MemoryMax" in s and int(s["TimeoutStopSec"]) >= 60
    assert "--concurrency=${WORKER_CONCURRENCY}" in s["ExecStart"]


def test_beat_keeps_its_schedule_file_on_the_writable_state_dir():
    assert "--schedule /var/lib/claramed/celerybeat-schedule" in _unit("claramed-beat")["Service"]["ExecStart"]


def test_caddyfile_proxies_to_loopback_with_security_headers():
    c = (NATIVE / "Caddyfile").read_text()
    assert "reverse_proxy 127.0.0.1:8000" in c and "Strict-Transport-Security" in c and "request_body" in c
    assert "claramed.example.com" in c, "domain must be an obvious placeholder to replace"


def _env_template():
    lines = (NATIVE / "claramed.env.example").read_text().splitlines()
    return dict(l.split("=", 1) for l in lines if "=" in l and not l.lstrip().startswith("#"))


def test_env_template_is_production_and_local_only():
    env = _env_template()
    assert env["APP_ENV"] == "production" and env["DEBUG"] == "false"
    assert env["STORAGE_SHARED_CONFIRMED"] == "true" and env["STORAGE_LOCAL_PATH"] == "/var/lib/claramed/storage"
    assert "@127.0.0.1:5432/" in env["DATABASE_URL"] and env["REDIS_URL"].startswith("redis://127.0.0.1")


def test_env_template_has_only_real_settings_and_only_placeholder_secrets():
    env = _env_template()
    fields = set(Settings.model_fields)
    unknown = [k for k in env if k not in fields and k not in EXTRA_ENV_KEYS]      # extra="ignore" would hide typos
    assert unknown == [], unknown
    for key in ("API_KEY_HASH_SECRET", "SECRET_KEY", "GROQ_API_KEY"):
        assert env[key].strip() in ("", "CHANGE_ME"), key
    assert "CHANGE_ME" in env["DATABASE_URL"]


@pytest.mark.parametrize("script", ["deploy/native/claramed-run.sh", "scripts/backup_native.sh",
                                    "scripts/update_native.sh"])
def test_helper_scripts_fail_fast(script):
    text = (ROOT / script).read_text()
    assert text.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in text, script


def test_run_wrapper_loads_the_env_file_as_the_service_user():
    t = (ROOT / "deploy/native/claramed-run.sh").read_text()
    assert "/etc/claramed/claramed.env" in t and "set -a" in t and "claramed" in t and "/opt/claramed/venv/bin" in t


def test_backup_and_update_scripts_do_the_essentials():
    b = (ROOT / "scripts/backup_native.sh").read_text()
    assert "pg_dump" in b and "-mtime" in b and "wc -c" in b
    u = (ROOT / "scripts/update_native.sh").read_text()
    for needle in ("pull --ff-only", "claramed-migrate", "systemctl restart", "post_deploy_check", "pip install"):
        assert needle in u, needle


DOC = (ROOT / "docs" / "DEPLOYMENT_NATIVE.md")


def test_runbook_references_only_files_that_exist():
    paths = set(re.findall(r"`((?:scripts|deploy|docs)/[\w./-]+)`", DOC.read_text()))
    assert paths
    assert sorted(p for p in paths if not (ROOT / p).exists()) == []


def test_runbook_covers_oracle_and_native_essentials():
    d = DOC.read_text()
    for needle in ("VM.Standard.A1.Flex", "Security List", "iptables", "uv python install 3.11", "systemctl",
                   "journalctl", "chmod 640", "post_deploy_check.py", "backup_native.sh", "Restore", "Rollback",
                   "claramed-run", "Pre-launch checklist", "pay-as-you-go", "single point of failure",
                   "not been run"):
        assert needle.lower() in d.lower(), needle
