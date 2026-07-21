import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from core.models.user import User
from api.dependencies.authorization import current_admin
from scripts.backup import create_backup, BACKUPS_DIR

router = APIRouter(prefix="/backups", tags=["Backups"])

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def trigger_backup(
    admin: User = Depends(current_admin)
):
    try:
        filename = create_backup("manual")
        return {"message": "Backup created successfully", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_backups(
    admin: User = Depends(current_admin)
):
    if not BACKUPS_DIR.exists():
        return []
    
    files = []
    for p in BACKUPS_DIR.glob("backup_*.tar.gz"):
        stat = p.stat()
        files.append({
            "filename": p.name,
            "size_bytes": stat.st_size,
            "created_at": stat.st_mtime
        })
    
    return sorted(files, key=lambda x: x["created_at"], reverse=True)

@router.get("/{filename}/download")
async def download_backup(
    filename: str,
    admin: User = Depends(current_admin)
):
    file_path = BACKUPS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
        
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/gzip"
    )
