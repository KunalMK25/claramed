"""docs/DEPLOYMENT_VM.md must only reference files and commands that exist, and cover the operational basics."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "docs" / "DEPLOYMENT_VM.md").read_text()


def test_every_referenced_repo_path_exists():
    paths = set(re.findall(r"`((?:scripts|deploy|docs)/[\w./-]+|docker-compose\.prod\.yml|\.env\.production\.example)`", DOC))
    assert paths, "doc should reference repo files"
    missing = sorted(p for p in paths if not (ROOT / p).exists())
    assert missing == [], missing


def test_runbook_covers_the_operational_basics():
    for needle in ("openssl rand -hex", "chmod 600 .env", "ufw", "docker compose -f docker-compose.prod.yml",
                   "register_client.py", "post_deploy_check.py", "backup.sh", "Restore", "Rollback",
                   "/api/v1/health/ready", "git pull", "Pre-launch checklist"):
        assert needle in DOC, needle


def test_runbook_states_the_known_limits_honestly():
    assert "single point of failure" in DOC.lower()
    assert "not been run" in DOC.lower() or "untested" in DOC.lower()
