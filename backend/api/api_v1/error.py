import uuid
from typing import Annotated, List

import crud.error as error_crud
from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import ListParams
from core.schemas.error import ErrorCreate, ErrorRead, ErrorReadAdmin, ErrorUpdate
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(
    prefix=settings.api.v1.error,
    tags=["Error"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
IsUser = Annotated[User, Depends(current_active_user)]


@router.get("", response_model=List[ErrorRead])
async def get_errors(db: Session, query: ListParams = Depends()):
    return await error_crud.get_errors(db, query.limit, query.offset, query.sorted)


@router.get("/search", response_model=List[ErrorRead])
async def search_errors(
    db: Session,
    query: ListParams = Depends(),
    q: str | None = Query(None, description="Search query"),
):
    return await error_crud.search_errors(db, q=q, limit=query.limit, offset=query.offset)


@router.get("/{error_id}", response_model=ErrorRead)
async def get_error(
    db: Session,
    error_id: uuid.UUID,
):
    error = await error_crud.get_error(db, error_id)
    if not error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Error not found"
        )
    return error


@router.get("/{error_id}/admin", response_model=ErrorReadAdmin)
async def get_error_admin(
    error_id: uuid.UUID,
    admin: AdminUser,
    db: Session,
):
    error = await error_crud.get_error(db, error_id)
    if not error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Error not found"
        )
    return error


@router.post("", response_model=ErrorReadAdmin, status_code=status.HTTP_201_CREATED)
async def create_error(
    data: ErrorCreate,
    db: Session,
    admin: AdminUser,
):
    return await error_crud.create_error(db, data, admin.id)


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_errors(
    db: Session,
    admin: AdminUser,
    file: UploadFile = File(),
):
    return await error_crud.import_errors(db, file, admin.id)


@router.patch("/{error_id}", response_model=ErrorReadAdmin)
async def update_error(
    error_id: uuid.UUID,
    data: ErrorUpdate,
    db: Session,
    admin: AdminUser,
):
    error = await error_crud.get_error(db, error_id)
    if not error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Error not found"
        )
    return await error_crud.update_error(db, error, data)


@router.delete("/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_errors(
    db: Session,
    admin: AdminUser,
):
    await error_crud.delete_all_errors(db)


@router.delete("/{error_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_error(
    error_id: uuid.UUID,
    db: Session,
    admin: AdminUser,
):
    error = await error_crud.get_error(db, error_id)
    if not error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Error not found"
        )
    await error_crud.delete_error(db, error)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_errors(
    list_error_id: Annotated[list[uuid.UUID], Query()],
    db: Session,
    admin: AdminUser,
):
    await error_crud.delete_errors(db, list_error_id)
