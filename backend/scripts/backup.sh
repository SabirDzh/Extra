#!/bin/bash
# Механизм создания бэкапов (недельных и месячных) с ротацией (хранить только 2 последних)

if [ "$1" != "weekly" ] && [ "$1" != "monthly" ]; then
    echo "Usage: $0 {weekly|monthly}"
    exit 1
fi

CATEGORY=$1
BACKUP_DIR="backups/$CATEGORY"

# Переходим в директорию backend, если скрипт запущен из корня
cd "$(dirname "$0")/.."

mkdir -p "$BACKUP_DIR"

# Чтение URL базы данных из .env
DB_URL=$(grep "APP_CONFIG__DB__URL=" .env | cut -d '=' -f 2-)
if [ -z "$DB_URL" ]; then
    echo "Error: APP_CONFIG__DB__URL not found in .env"
    exit 1
fi

# Убираем +asyncpg чтобы утилита pg_dump могла подключиться
PG_URL=${DB_URL/+asyncpg/}

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.sql.gz"

echo "Creating $CATEGORY backup: $BACKUP_FILE"
# Используем pg_dump для создания бэкапа и сразу архивируем его с помощью gzip
pg_dump "$PG_URL" | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup successfully created."
else
    echo "Error creating backup!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Ротация: оставляем только 2 самых новых бэкапа
echo "Cleaning up old $CATEGORY backups (keeping only the 2 most recent)..."

# ls -t сортирует файлы по времени изменения (новые в начале)
# tail -n +3 берет файлы начиная с 3-го (то есть пропускает 2 самых новых)
# xargs -I {} rm -- {} удаляет эти файлы
ls -t "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | tail -n +3 | xargs -I {} rm -- {}

echo "Backup rotation finished."
