#!/bin/bash
set -euo pipefail
umask 077

: "${POSTGRES_DB:?POSTGRES_DB sozlanmagan}"
: "${POSTGRES_USER:?POSTGRES_USER sozlanmagan}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD sozlanmagan}"
: "${BACKUP_AGE_RECIPIENT:?BACKUP_AGE_RECIPIENT sozlanmagan}"
: "${DJANGO_MEDIA_ROOT:?DJANGO_MEDIA_ROOT sozlanmagan}"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/distribyutsiya}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DB_TARGET="$BACKUP_DIR/distribyutsiya-$STAMP.dump.age"
MEDIA_TARGET="$BACKUP_DIR/media-$STAMP.tar.gz.age"
DB_TEMP="$(mktemp "$BACKUP_DIR/.db-backup.XXXXXX")"
MEDIA_TEMP="$(mktemp "$BACKUP_DIR/.media-backup.XXXXXX")"

cleanup() {
    rm -f "$DB_TEMP" "$MEDIA_TEMP"
}
trap cleanup EXIT HUP INT TERM

export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump --host "${POSTGRES_HOST:-127.0.0.1}" \
    --port "${POSTGRES_PORT:-5432}" \
    --username "$POSTGRES_USER" \
    --format=custom \
    "$POSTGRES_DB" | age --recipient "$BACKUP_AGE_RECIPIENT" --output "$DB_TEMP"
unset PGPASSWORD

tar -C "$(dirname "$DJANGO_MEDIA_ROOT")" -czf - "$(basename "$DJANGO_MEDIA_ROOT")" \
    | age --recipient "$BACKUP_AGE_RECIPIENT" --output "$MEDIA_TEMP"

mv "$DB_TEMP" "$DB_TARGET"
mv "$MEDIA_TEMP" "$MEDIA_TARGET"
find "$BACKUP_DIR" -type f \( -name 'distribyutsiya-*.dump.age' -o -name 'media-*.tar.gz.age' \) -mtime +30 -delete
printf 'Zaxira yaratildi: %s va %s\n' "$DB_TARGET" "$MEDIA_TARGET"
