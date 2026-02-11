import io
import os
from pathlib import Path

from PIL import Image
from fastapi import UploadFile
from core.config import BASE_DIR

AVATAR_UPLOAD_DIR = BASE_DIR / "media" / "user_img"

MAX_AVATAR_BYTES = 5 * 1024 * 1024
AVATAR_SIZE_PX = 256

def save_user_avatar(user_id: str, file: UploadFile) -> str:
    os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise ValueError("Invalid file type")

    content = file.file.read(MAX_AVATAR_BYTES + 1)
    if len(content) > MAX_AVATAR_BYTES:
        raise ValueError("File too large")

    img = Image.open(io.BytesIO(content))
    img = img.convert("RGB")

    width, height = img.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((AVATAR_SIZE_PX, AVATAR_SIZE_PX), Image.Resampling.LANCZOS)

    file_name = f"{user_id}.jpg"
    file_path = AVATAR_UPLOAD_DIR / file_name

    tmp_path = file_path.with_suffix(".jpg.tmp")
    img.save(tmp_path, format="JPEG", quality=85, optimize=True)
    os.replace(tmp_path, file_path)

    return f"/media/user_img/{file_name}"
