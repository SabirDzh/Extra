from core.config import settings
from fastapi import APIRouter

router = APIRouter(prefix=settings.api.v1.certificates, tags=["Certificates"])


@router.get("/")
async def get_certificate():
    pass


@router.get("/{certificate_id}/download")
async def download_certificate():
    pass
