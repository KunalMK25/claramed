#!/usr/bin/env bash
# Update a native install: pull the code, refresh dependencies, migrate, restart, and check.
# Run on the VM as a sudo-capable user:   sudo /opt/claramed/app/scripts/update_native.sh [branch]
# To roll back: `git -C /opt/claramed/app checkout <previous commit>` and run this script again.
set -euo pipefail

APP=/opt/claramed/app
BRANCH="${1:-}"

sudo -u claramed git -C "$APP" fetch --all --prune
if [ -n "$BRANCH" ]; then
    sudo -u claramed git -C "$APP" checkout "$BRANCH"
fi
sudo -u claramed git -C "$APP" pull --ff-only

# Same dependency step as first setup (the venv was created with pip included); satisfied packages are skipped.
sudo -u claramed /opt/claramed/venv/bin/python -m pip install --quiet -r "$APP/requirements-backend.txt"

systemctl restart claramed-migrate      # re-runs `alembic upgrade head`
systemctl restart claramed-api claramed-worker claramed-beat

sleep 8
systemctl --no-pager --lines=0 status claramed-api claramed-worker claramed-beat | grep -E "●|Active:"
echo "Now run: python scripts/post_deploy_check.py --base-url https://<your-domain>   (from your own machine)"
