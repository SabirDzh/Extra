import uuid

from pydantic import BaseModel, Field


class CourseRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    raiting: float


class CourseCreate(BaseModel):
    pass


class CourseUpdate(BaseModel):
    pass
