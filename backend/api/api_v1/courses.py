from core.config import settings
from fastapi import APIRouter

router = APIRouter(
    prefix=settings.api.v1.courses,
    tags=["/courses"],
)


@router.get("")
async def get_list_courses():
    pass


@router.get("/{course_id}")
async def get_course():
    pass


@router.get("/my/progress")
async def get_my_progress():
    pass


@router.post("/{course_id}/certificate")
async def certificate_generate():
    pass
