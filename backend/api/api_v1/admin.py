from core.config import settings
from fastapi import APIRouter

router = APIRouter(
    prefix=settings.api.v1.admin,
    tags=["Admin"],
)


@router.get("/reviews")
async def get_list_reviews():
    pass


@router.post("/reviews/{submission_id}")
async def guestion_status():
    pass
