#!/usr/bin/env bash
# Dump the ClaraMed database (native install) to /var/backups/claramed, keep KEEP_DAYS days (default 14).
# Run as root from cron, e.g. nightly:   17 2 * * * /opt/claramed/app/scripts/backup_native.sh >> /var/log/claramed-backup.log 2>&1
# Copy /var/backups/claramed off the VM too: a backup on the same disk does not survive losing the disk.
set -euo pipefail

DIR="${BACKUP_DIR:-/var/backups/claramed}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
mkdir -p "$DIR"
chmod 700 "$DIR"

sudo -u postgres pg_dump --no-owner claramed | gzip > "$DIR/claramed-${STAMP}.sql.gz"

# Refuse to keep an empty or truncated dump.
if [ "$(gzip -dc "$DIR/claramed-${STAMP}.sql.gz" | wc -c)" -lt 1000 ]; then
    rm -f "$DIR/claramed-${STAMP}.sql.gz"
    echo "backup failed: dump is empty" >&2
    exit 1
fi

find "$DIR" -name 'claramed-*.sql.gz' -mtime +"${KEEP_DAYS}" -delete
echo "backup ok: $DIR/claramed-${STAMP}.sql.gz"
