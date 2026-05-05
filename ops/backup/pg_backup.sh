#!/usr/bin/env bash
set -euo pipefail

# Full PostgreSQL backup with rotation.
# Usage:
#   source /etc/extra_backend/backup.env
#   ./pg_backup.sh

if [[ -z "${BACKUP_CONTAINER_NAME:-}" ]]; then
  echo "BACKUP_CONTAINER_NAME is required"
  exit 1
fi
if [[ -z "${BACKUP_DB_NAME:-}" ]]; then
  echo "BACKUP_DB_NAME is required"
  exit 1
fi
if [[ -z "${BACKUP_DB_USER:-}" ]]; then
  echo "BACKUP_DB_USER is required"
  exit 1
fi

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/extra_backend/postgres}"
RETENTION_DAYS_DAILY="${RETENTION_DAYS_DAILY:-35}"
RETENTION_DAYS_WEEKLY="${RETENTION_DAYS_WEEKLY:-84}"
RETENTION_DAYS_MONTHLY="${RETENTION_DAYS_MONTHLY:-365}"

mkdir -p "${BACKUP_ROOT}/daily" "${BACKUP_ROOT}/weekly" "${BACKUP_ROOT}/monthly"

TS="$(date +%Y-%m-%d_%H-%M-%S)"
FILE_BASE="${BACKUP_DB_NAME}_${TS}"
DUMP_PATH="${BACKUP_ROOT}/daily/${FILE_BASE}.dump"

if ! docker ps --format '{{.Names}}' | grep -qx "${BACKUP_CONTAINER_NAME}"; then
  echo "PostgreSQL container '${BACKUP_CONTAINER_NAME}' is not running"
  exit 1
fi

# -Fc gives compressed custom format (pg_restore friendly).
docker exec "${BACKUP_CONTAINER_NAME}" pg_dump \
  -U "${BACKUP_DB_USER}" \
  -d "${BACKUP_DB_NAME}" \
  -Fc > "${DUMP_PATH}"

# Optional checksum file.
sha256sum "${DUMP_PATH}" > "${DUMP_PATH}.sha256"

# Weekly snapshot each Sunday (7)
if [[ "$(date +%u)" == "7" ]]; then
  cp "${DUMP_PATH}" "${BACKUP_ROOT}/weekly/${FILE_BASE}.dump"
  cp "${DUMP_PATH}.sha256" "${BACKUP_ROOT}/weekly/${FILE_BASE}.dump.sha256"
fi

# Monthly snapshot on day 01
if [[ "$(date +%d)" == "01" ]]; then
  cp "${DUMP_PATH}" "${BACKUP_ROOT}/monthly/${FILE_BASE}.dump"
  cp "${DUMP_PATH}.sha256" "${BACKUP_ROOT}/monthly/${FILE_BASE}.dump.sha256"
fi

# Rotation
find "${BACKUP_ROOT}/daily" -type f -name '*.dump' -mtime +"${RETENTION_DAYS_DAILY}" -delete
find "${BACKUP_ROOT}/daily" -type f -name '*.sha256' -mtime +"${RETENTION_DAYS_DAILY}" -delete

find "${BACKUP_ROOT}/weekly" -type f -name '*.dump' -mtime +"${RETENTION_DAYS_WEEKLY}" -delete
find "${BACKUP_ROOT}/weekly" -type f -name '*.sha256' -mtime +"${RETENTION_DAYS_WEEKLY}" -delete

find "${BACKUP_ROOT}/monthly" -type f -name '*.dump' -mtime +"${RETENTION_DAYS_MONTHLY}" -delete
find "${BACKUP_ROOT}/monthly" -type f -name '*.sha256' -mtime +"${RETENTION_DAYS_MONTHLY}" -delete

echo "Backup completed: ${DUMP_PATH}"
