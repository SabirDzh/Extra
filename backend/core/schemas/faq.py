import uuid

from pydantic import BaseModel, ConfigDict, Field


class FAQBase(BaseModel):
    question: str = Field(max_length=512)
    answer: str
    order_index: int = 0
    is_published: bool = True


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    question: str | None = Field(None, max_length=512)
    answer: str | None = None
    order_index: int | None = None
    is_published: bool | None = None


class FAQRead(FAQBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
