import os
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from core.config import settings

BACKUPS_DIR = Path(__file__).resolve().parent.parent / "backups"
MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"


def create_backup(backup_type: str = "manual") -> str:
    """
    Создает бэкап базы данных и директории media.
    Типы бэкапов: manual, weekly, monthly
    """
    if not BACKUPS_DIR.exists():
        BACKUPS_DIR.mkdir(parents=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{backup_type}_{timestamp}.tar.gz"
    backup_path = BACKUPS_DIR / backup_filename
    
    # 1. Дамп базы данных (используем pg_dump)
    # Формируем строку подключения из settings.db.url
    # settings.db.url - это PostgresDsn (pydantic), приводим к строке
    db_url_str = str(settings.db.url)
    # Для pg_dump нужно заменить asyncpg на обычный postgresql
    db_url_str = db_url_str.replace("+asyncpg", "")
    
    db_dump_path = BACKUPS_DIR / f"db_dump_{timestamp}.sql"
    
    try:
        # Запускаем pg_dump
        subprocess.run(
            ["pg_dump", db_url_str, "-F", "c", "-f", str(db_dump_path)],
            check=True,
            capture_output=True
        )
        
        # 2. Создаем tar.gz архив, добавляя в него SQL-дамп и папку media
        with tarfile.open(backup_path, "w:gz") as tar:
            # Добавляем дамп БД
            tar.add(db_dump_path, arcname=db_dump_path.name)
            
            # Добавляем папку media, если она существует
            if MEDIA_DIR.exists():
                tar.add(MEDIA_DIR, arcname="media")
                
    finally:
        # Удаляем временный файл SQL-дампа
        if db_dump_path.exists():
            db_dump_path.unlink()
            
    # После создания бэкапа запускаем ротацию
    rotate_backups()
    
    return backup_filename


def rotate_backups():
    """
    Оставляет максимум 2 недельных и 2 месячных бэкапа.
    Остальные удаляются. Manual бэкапы не ротируются (или можно настроить).
    """
    if not BACKUPS_DIR.exists():
        return
        
    backups = list(BACKUPS_DIR.glob("backup_*.tar.gz"))
    
    weekly_backups = sorted([b for b in backups if "weekly" in b.name], key=lambda x: x.stat().st_mtime, reverse=True)
    monthly_backups = sorted([b for b in backups if "monthly" in b.name], key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Оставляем только 2 последних
    weekly_to_delete = weekly_backups[2:]
    monthly_to_delete = monthly_backups[2:]
    
    for b in weekly_to_delete:
        b.unlink()
        
    for b in monthly_to_delete:
        b.unlink()

if __name__ == "__main__":
    import sys
    b_type = sys.argv[1] if len(sys.argv) > 1 else "manual"
    created_file = create_backup(b_type)
    print(f"Created backup: {created_file}")
