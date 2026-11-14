#!/usr/bin/env bash
# Run a command as the claramed user with the production environment loaded, e.g.:
#   sudo claramed-run python scripts/register_client.py --help
#   sudo claramed-run alembic current
# Install once:  sudo install -m 755 deploy/native/claramed-run.sh /usr/local/bin/claramed-run
set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: sudo claramed-run <command> [args...]   (python, alembic, celery ... from the app venv)" >&2
    exit 2
fi

exec sudo -u claramed -H bash -c '
    set -euo pipefail
    set -a; . /etc/claramed/claramed.env; set +a
    export PATH=/opt/claramed/venv/bin:$PATH
    cd /opt/claramed/app
    exec "$@"
' _ "$@"
