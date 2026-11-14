#!/usr/bin/env bash
# Dump the ClaraMed database to backups/, keep the newest KEEP_DAYS days (default 14).
# Run from the repo directory on the VM, e.g. nightly from cron:
#   17 2 * * * cd /opt/claramed && ./scripts/backup.sh >> backups/backup.log 2>&1
# Copy backups/ off the VM too (a backup on the same disk does not survive losing the disk).
set -euo pipefail

cd "$(dirname "$0")/.."
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
mkdir -p backups

docker compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U claramed -d claramed --no-owner | gzip > "backups/claramed-${STAMP}.sql.gz"

# Refuse to keep an empty or truncated dump.
if [ "$(gzip -dc "backups/claramed-${STAMP}.sql.gz" | wc -c)" -lt 1000 ]; then
    rm -f "backups/claramed-${STAMP}.sql.gz"
    echo "backup failed: dump is empty" >&2
    exit 1
fi

find backups -name 'claramed-*.sql.gz' -mtime +"${KEEP_DAYS}" -delete
echo "backup ok: backups/claramed-${STAMP}.sql.gz"
