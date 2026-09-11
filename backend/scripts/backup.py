"""Create and retain database/media backup archives."""

import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from core.config import settings

BACKUPS_DIR = Path(__file__).resolve().parent.parent / "backups"
MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"


def create_backup(backup_type: str = "manual") -> str:
    """Create a database and media archive.

    Args:
        backup_type: Name used to identify the backup retention group.

    Returns:
        Created archive filename.

    Raises:
        subprocess.CalledProcessError: If ``pg_dump`` cannot create a dump.
        subprocess.TimeoutExpired: If ``pg_dump`` exceeds the configured limit.
    """
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{backup_type}_{timestamp}.tar.gz"
    backup_path = BACKUPS_DIR / backup_filename
    db_url_str = str(settings.db.url)
    db_url_str = db_url_str.replace("+asyncpg", "")
    db_dump_path = BACKUPS_DIR / f"db_dump_{timestamp}.sql"

    try:
        subprocess.run(
            ["pg_dump", db_url_str, "-F", "c", "-f", str(db_dump_path)],
            check=True,
            capture_output=True,
            timeout=settings.backup.command_timeout_seconds,
        )
        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(db_dump_path, arcname=db_dump_path.name)
            if MEDIA_DIR.exists():
                tar.add(MEDIA_DIR, arcname="media")
    finally:
        if db_dump_path.exists():
            db_dump_path.unlink()

    rotate_backups()
    return backup_filename


def rotate_backups() -> None:
    """Keep only the two newest weekly and monthly backup archives."""
    if not BACKUPS_DIR.exists():
        return

    backups = list(BACKUPS_DIR.glob("backup_*.tar.gz"))
    weekly_backups = sorted(
        (backup for backup in backups if "weekly" in backup.name),
        key=lambda backup: backup.stat().st_mtime,
        reverse=True,
    )
    monthly_backups = sorted(
        (backup for backup in backups if "monthly" in backup.name),
        key=lambda backup: backup.stat().st_mtime,
        reverse=True,
    )

    for backup in [*weekly_backups[2:], *monthly_backups[2:]]:
        backup.unlink()

if __name__ == "__main__":
    import sys
    b_type = sys.argv[1] if len(sys.argv) > 1 else "manual"
    created_file = create_backup(b_type)
    print(f"Created backup: {created_file}")
