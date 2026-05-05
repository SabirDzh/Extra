#!/usr/bin/env bash
set -euo pipefail

# Restore PostgreSQL backup created by pg_backup.sh
# Usage:
#   source /etc/extra_backend/backup.env
#   ./pg_restore.sh /path/to/backup.dump [target_db]

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/backup.dump [target_db]"
  exit 1
fi

if [[ -z "${BACKUP_CONTAINER_NAME:-}" ]]; then
  echo "BACKUP_CONTAINER_NAME is required"
  exit 1
fi
if [[ -z "${BACKUP_DB_USER:-}" ]]; then
  echo "BACKUP_DB_USER is required"
  exit 1
fi

DUMP_FILE="$1"
TARGET_DB="${2:-${BACKUP_DB_NAME:-}}"

if [[ -z "${TARGET_DB}" ]]; then
  echo "Target DB is not set. Pass as 2nd arg or set BACKUP_DB_NAME"
  exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "Dump file not found: ${DUMP_FILE}"
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${BACKUP_CONTAINER_NAME}"; then
  echo "PostgreSQL container '${BACKUP_CONTAINER_NAME}' is not running"
  exit 1
fi

# Restore with clean to drop/recreate objects.
cat "${DUMP_FILE}" | docker exec -i "${BACKUP_CONTAINER_NAME}" pg_restore \
  -U "${BACKUP_DB_USER}" \
  -d "${TARGET_DB}" \
  --clean \
  --if-exists \
  --no-owner

echo "Restore completed into database: ${TARGET_DB}"
