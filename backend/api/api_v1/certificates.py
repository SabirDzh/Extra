import uuid
from typing import Annotated

from core.authentication.fastapi_users import current_active_user
from core.certificate_pdf import async_generate_certificate_pdf
from core.models.block import Block
from core.models.certificates import Certificate
from core.models.course import Course
from core.models.db_helper import db_helper
from core.models.progress import UserBlockProgress
from core.models.user import User
from core.schemas.certificate import CertificateRead
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from core.config import settings

from api.dependencies.authorization import current_course_allowed_user
from Domain.Enums.user_role import UserRole

router = APIRouter(
    prefix=settings.api.v1.certificates,
    tags=["Certificates"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
CourseAllowedUser = Annotated[User, Depends(current_course_allowed_user)]


@router.post(
    "/courses/{course_id}/generate",
    response_model=CertificateRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_certificate(
    course_id: uuid.UUID, db: Session, user: CourseAllowedUser
):
    course = await db.get(Course, course_id, options=[selectinload(Course.blocks)])
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    existing = (
        await db.execute(
            select(Certificate).where(
                Certificate.user_id == user.id,
                Certificate.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    total = len(course.blocks)
    if total == 0:
        raise HTTPException(status_code=400, detail="Course has no blocks")

    block_ids = [b.id for b in course.blocks]
    completed = (
        await db.execute(
            select(func.count(UserBlockProgress.id)).where(
                UserBlockProgress.user_id == user.id,
                UserBlockProgress.block_id.in_(block_ids),
                UserBlockProgress.is_completed == True,
            )
        )
    ).scalar()

    if completed < total:
        raise HTTPException(
            status_code=400, detail=f"Course not fully completed ({completed}/{total})"
        )

    cert = Certificate(user_id=user.id, course_id=course_id)
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    return cert


@router.get("/courses/{course_id}/certificate", response_model=CertificateRead)
async def get_certificate(
    course_id: uuid.UUID, db: Session, user: CourseAllowedUser
):
    cert = (
        await db.execute(
            select(Certificate).where(
                Certificate.user_id == user.id,
                Certificate.course_id == course_id,
            )
        )
    ).scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return cert


@router.get("/{certificate_number}/download")
async def download_certificate(
    certificate_number: str,
    db: Session,
    user: User = Depends(current_active_user),
):
    cert = (
        await db.execute(
            select(Certificate)
            .where(Certificate.certificate_number == certificate_number)
            .options(
                selectinload(Certificate.user),
                selectinload(Certificate.course),
            )
        )
    ).scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if user.role != UserRole.admin and cert.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    pdf_bytes = await async_generate_certificate_pdf(
        full_name=cert.user.full_name,
        course_title=cert.course.title,
        certificate_number=cert.certificate_number,
        issued_at=cert.issued_at,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificate_{cert.certificate_number}.pdf"'
        },
    )
