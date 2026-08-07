#!/usr/bin/env bash
# Back up the production database and the certificate store.
#
# What is worth backing up, and what is not:
#
#   db-data     Yes. Every transcript, account and job. Irreplaceable.
#   caddy-data  Yes. TLS certificates. Replaceable, but Let's Encrypt
#               rate-limits re-issuance, so restoring beats re-requesting.
#   api-data    No. Working files and the Whisper model cache — both are
#               re-downloaded on demand, and the models are gigabytes.
#
# Usage:
#   ./scripts/backup.sh [destination-directory]
#
# Restore a database dump with:
#   gunzip -c db-YYYYMMDD-HHMMSS.sql.gz | docker compose -f docker-compose.prod.yml \
#     exec -T db psql -U research_hub research_hub

set -euo pipefail

DESTINATION="${1:-./backups}"
COMPOSE_FILE="$(dirname "$0")/../docker-compose.prod.yml"
ENV_FILE="$(dirname "$0")/../.env.production"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

if [ ! -f "$ENV_FILE" ]; then
	echo "No .env.production found — is this the production host?" >&2
	exit 1
fi

# shellcheck disable=SC1090
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"
POSTGRES_USER="${POSTGRES_USER:-research_hub}"
POSTGRES_DB="${POSTGRES_DB:-research_hub}"

mkdir -p "$DESTINATION"

echo "Dumping database…"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
	pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip >"$DESTINATION/db-$STAMP.sql.gz"

echo "Archiving certificates…"
docker run --rm \
	-v research-hub_caddy-data:/data:ro \
	-v "$(cd "$DESTINATION" && pwd)":/backup \
	alpine tar czf "/backup/caddy-$STAMP.tar.gz" -C /data .

# A backup you never prune becomes a disk-full incident of its own.
find "$DESTINATION" -name 'db-*.sql.gz' -mtime +30 -delete
find "$DESTINATION" -name 'caddy-*.tar.gz' -mtime +30 -delete

echo "Done:"
ls -lh "$DESTINATION" | tail -4
echo
echo "A backup that has never been restored is a hope, not a backup."
echo "Restore one into a scratch database before you need to."
