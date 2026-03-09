import uuid
from typing import Annotated, List

from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.faq import FAQCreate, FAQRead, FAQUpdate
from crud import faq as faq_crud
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(
    prefix=settings.api.v1.faq,
    tags=["FAQ"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]


@router.get("/", response_model=List[FAQRead])
async def list_faqs(
    db: Session,
    pagination: PaginationParams = Depends(),
):
    return await faq_crud.get_faqs(db, offset=pagination.offset, limit=pagination.limit)


@router.get("/search", response_model=List[FAQRead])
async def search_faqs(
    db: Session,
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, description="Search query"),
):
    return await faq_crud.search_faqs(
        db, q=q, offset=pagination.offset, limit=pagination.limit
    )


@router.post("/", response_model=FAQRead, status_code=status.HTTP_201_CREATED)
async def create_faq(
    data: FAQCreate,
    db: Session,
    admin: AdminUser,
):
    return await faq_crud.create_faq(db, data)


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_faqs(
    db: Session,
    admin: AdminUser,
    file: UploadFile = File(),
):
    return await faq_crud.import_faqs(db, file)


@router.get("/{faq_id}", response_model=FAQRead)
async def get_faq(faq_id: uuid.UUID, db: Session):
    faq = await faq_crud.get_faq(db, faq_id)
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found"
        )
    return faq


@router.patch("/{faq_id}", response_model=FAQRead)
async def update_faq(
    faq_id: uuid.UUID,
    data: FAQUpdate,
    db: Session,
    admin: AdminUser,
):
    faq = await faq_crud.get_faq(db, faq_id)
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found"
        )

    return await faq_crud.update_faq(db, faq, data)


@router.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
):
    faq = await faq_crud.get_faq(db, faq_id)
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found"
        )
    await faq_crud.delete_faq(db, faq)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_faqs(
    data: Annotated[list[uuid.UUID], Query()],
    db: Session,
    admin: AdminUser,
):
    await faq_crud.bulk_delete_faqs(db, data)
