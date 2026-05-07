import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RecommendationBase(BaseModel):
    title: str
    description: str | None = None
    created_at: datetime.datetime


class RecommendationRead(RecommendationBase):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


class RecommendationListRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)


class RecommendationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1)
    is_published: bool = True

    model_config = ConfigDict(
        from_attributes=True,
    )


class RecommendationUpdate(BaseModel):
    title: str | None = Field(min_length=1, max_length=256)
    description: str | None = Field(min_length=1)
    is_published: bool | None = True


class RecommendationReadAdmin(RecommendationBase):
    id: uuid.UUID
    is_published: bool = True
    updated_at: datetime.datetime
    created_by: uuid.UUID
    model_config = ConfigDict(from_attributes=True)
