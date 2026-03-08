import uuid

from pydantic import BaseModel, Field


class TermResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str


class TermRequest(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str
