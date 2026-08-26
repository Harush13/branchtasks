#!/usr/bin/env bash
# Nightly backup for the docker-compose stack (spec §13 Phase 7): a gzipped
# pg_dump of the `db` service plus a tarball of the `media` volume
# (attachments — spec §3.4 — live only there, never in Postgres). Intended
# to run via host crontab, from the repo root:
#
#   0 3 * * * cd /path/to/branchtasks && ./scripts/backup.sh >> /var/log/branchtasks-backup.log 2>&1
#
# Restore: `gunzip -c branchtasks-<ts>.sql.gz | docker compose exec -T db
# psql -U branchtasks branchtasks` for the DB; untar media-<ts>.tar.gz into
# the `media` volume's mountpoint for attachments.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"

docker compose exec -T db pg_dump -U branchtasks branchtasks \
    | gzip > "$BACKUP_DIR/branchtasks-$TIMESTAMP.sql.gz"

# --entrypoint bypasses docker-entrypoint.sh (migrate+collectstatic) — this
# is a throwaway container just to reach the shared `media` volume.
docker compose run --rm --no-deps --entrypoint tar -v "$(pwd)/$BACKUP_DIR:/backup" web \
    czf "/backup/media-$TIMESTAMP.tar.gz" -C /app media

# Retention: delete anything older than RETENTION_DAYS from both backup kinds.
find "$BACKUP_DIR" -name 'branchtasks-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name 'media-*.tar.gz' -mtime "+$RETENTION_DAYS" -delete

echo "Backed up DB to $BACKUP_DIR/branchtasks-$TIMESTAMP.sql.gz and media to $BACKUP_DIR/media-$TIMESTAMP.tar.gz"
