import os
import shutil
from pathlib import Path
from fastapi import UploadFile
from core.config import BASE_DIR

AVATAR_UPLOAD_DIR = BASE_DIR / "media" / "user_img"

def save_user_avatar(user_id: str, file: UploadFile) -> str:
    os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)
    
    file_extension = Path(file.filename).suffix
    file_name = f"{user_id}{file_extension}"
    file_path = AVATAR_UPLOAD_DIR / file_name
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return f"/media/user_img/{file_name}"
