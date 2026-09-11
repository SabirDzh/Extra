"""Administrative endpoints for creating and downloading backups."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from api.dependencies.authorization import current_admin
from core.models.user import User
from scripts.backup import create_backup, BACKUPS_DIR

router = APIRouter(prefix="/backups", tags=["Backups"])
logger = logging.getLogger(__name__)


def _get_backup_path(filename: str) -> Path:
    """Resolve a listed backup filename without permitting path traversal.

    Args:
        filename: Filename supplied by the administrative client.

    Returns:
        Validated archive path.

    Raises:
        HTTPException: If the filename is not a known backup archive.
    """
    backups_dir = BACKUPS_DIR.resolve()
    candidate = (backups_dir / filename).resolve()
    is_archive = filename.startswith("backup_") and filename.endswith(".tar.gz")
    if (
        not is_archive
        or candidate.parent != backups_dir
        or not candidate.exists()
        or not candidate.is_file()
    ):
        raise HTTPException(status_code=404, detail="Backup not found")
    return candidate


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def trigger_backup(
    admin: User = Depends(current_admin)
):
    try:
        filename = await asyncio.to_thread(create_backup, "manual")
        return {"message": "Backup created successfully", "filename": filename}
    except Exception:
        logger.exception("Manual backup creation failed")
        raise HTTPException(
            status_code=500,
            detail="Backup creation failed",
        ) from None


@router.get("/")
async def list_backups(
    admin: User = Depends(current_admin)
):
    if not BACKUPS_DIR.exists():
        return []
    
    files = [
        {
            "filename": backup.name,
            "size_bytes": backup.stat().st_size,
            "created_at": backup.stat().st_mtime,
        }
        for backup in BACKUPS_DIR.glob("backup_*.tar.gz")
    ]
    return sorted(files, key=lambda x: x["created_at"], reverse=True)


@router.get("/{filename}/download")
async def download_backup(
    filename: str,
    admin: User = Depends(current_admin)
):
    file_path = _get_backup_path(filename)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/gzip"
    )
