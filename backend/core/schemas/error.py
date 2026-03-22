import datetime
import uuid

from pydantic import BaseModel, Field


class ErrorBase(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    description: str = Field(max_length=2048)
    image: str | None = None
    is_published: bool = True
    order_index: int = Field(ge=0)


class ErrorRead(ErrorBase):
    id: uuid.UUID
    created_at: datetime.datetime


class ErrorReadAdmin(ErrorRead):
    created_by: uuid.UUID
    updated_at: datetime.datetime


class ErrorCreate(ErrorBase):
    pass


class ErrorUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=512)
    description: str | None = Field(None, max_length=2048)
    is_published: bool | None = None
    order_index: int | None = Field(None, ge=0)
