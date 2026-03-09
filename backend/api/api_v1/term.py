import uuid
from typing import Annotated

import crud.term as term_crud
from core.authentication.fastapi_users import current_active_user
from core.config import settings
from core.models.db_helper import db_helper
from core.models.user import User
from core.schemas.base import PaginationParams
from core.schemas.term import TermRequest, TermResponse
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from utils.product import current_admin

router = APIRouter(
    prefix=settings.api.v1.term,
    tags=["Terms"],
)

Session = Annotated[AsyncSession, Depends(db_helper.session_getter)]
AdminUser = Annotated[User, Depends(current_admin)]
IsUser = Annotated[User, Depends(current_active_user)]


@router.get("", response_model=list[TermResponse])
async def get_terms(session: Session, pagination: Annotated[PaginationParams, Query()]):
    return await term_crud.get_terms(session, pagination)


@router.get("/{term_id}", response_model=TermResponse)
async def get_term(
    session: Session, term_id: Annotated[uuid.UUID, Path()], user: IsUser
):
    term = await term_crud.get_term(session, term_id)
    if term is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Termin not found",
        )
    return term


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TermResponse)
async def create_term(
    session: Session,
    term: TermRequest,
    admin: AdminUser,
):
    existing_term = await term_crud.get_term_by_title(session, term.title)
    if existing_term is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Termin already exists",
        )
    return await term_crud.create_term(
        session,
        term,
    )


@router.patch("/{term_id}", response_model=TermResponse)
async def update_term(
    session: Session,
    term_id: uuid.UUID,
    term: TermRequest,
    admin: AdminUser,
):
    data = await term_crud.update_term(session, term_id, term)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Termin not found",
        )
    return data


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_term(
    session: Session,
    term_id: uuid.UUID,
    admin: AdminUser,
):
    term = await term_crud.get_term(session, term_id)
    if term is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Termin not found",
        )
    await term_crud.delete_term(session, term_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_terms(
    session: Session,
    terms_id: Annotated[list[uuid.UUID], Query()],
    admin: AdminUser,
):
    return await term_crud.delete_terms(session, terms_id)


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_terms(
    session: Session,
    admin: AdminUser,
    file: UploadFile = File(),
):
    return await term_crud.import_terms(session, file)
