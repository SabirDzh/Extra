import uuid
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    title: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=1024)] = ""
    is_published: bool = True


class CourseUpdate(BaseModel):
    title: Annotated[str | None, Field(max_length=256)] = None
    description: Annotated[str | None, Field(max_length=1024)] = None
    is_published: Optional[bool] = None


class CourseRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    is_published: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CourseProgress(BaseModel):
    completed: Optional[int]
    total: int
    percent: float
