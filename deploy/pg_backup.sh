#!/usr/bin/env bash
# MuseAI PostgreSQL backup.
#
# Usage:
#   BACKUP_DIR=/var/backups/museai bash ./pg_backup.sh
#
# Connection resolution order (no passwords are hardcoded here):
#   1. PG_CONTAINER  — name of the docker compose PostgreSQL container;
#                      pg_dump runs inside it with the container's own auth.
#   2. DATABASE_URL  — SQLAlchemy-style URL exported by the caller (commonly
#                      loaded from repository-root .env); the async driver
#                      suffix (+asyncpg) is stripped for pg_dump.
#   3. libpq env     — PGHOST/PGPORT/PGUSER/PGPASSWORD or ~/.pgpass.
#
# Env vars:
#   BACKUP_DIR      target directory (default /var/backups/museai)
#   RETENTION_DAYS  days to keep old dumps (default 7)
#   DB_NAME         database name (default museai)
#   PG_CONTAINER    optional docker container name
#   PGUSER          database role inside PG_CONTAINER (default museai)
#
# Exits non-zero on any failure; prints the backup file path on success.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/museai}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DB_NAME="${DB_NAME:-museai}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S_%N)"
OUT_FILE="${BACKUP_DIR}/museai_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"
TMP_FILE="$(mktemp "${BACKUP_DIR}/.museai_${TIMESTAMP}.XXXXXX.sql.gz")"
cleanup() {
    rm -f -- "${TMP_FILE:-}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' HUP TERM

if [ -n "${PG_CONTAINER:-}" ]; then
    docker exec "$PG_CONTAINER" pg_dump --no-owner -U "${PGUSER:-museai}" "$DB_NAME" | gzip > "$TMP_FILE"
elif [ -n "${DATABASE_URL:-}" ]; then
    PG_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
    PG_URL="${PG_URL/postgres+asyncpg:\/\//postgresql://}"
    pg_dump --no-owner "$PG_URL" | gzip > "$TMP_FILE"
else
    pg_dump --no-owner "$DB_NAME" | gzip > "$TMP_FILE"
fi

# A failed pg_dump aborts above via pipefail. Validate the temporary gzip
# before atomically publishing it, so no partial final-name file is left.
if [ ! -s "$TMP_FILE" ]; then
    echo "ERROR: temporary backup file is empty" >&2
    exit 1
fi
gzip -t "$TMP_FILE"
mv -- "$TMP_FILE" "$OUT_FILE"
TMP_FILE=""
trap - EXIT INT HUP TERM

find "$BACKUP_DIR" -name 'museai_*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
printf '%s\n' "$OUT_FILE"
