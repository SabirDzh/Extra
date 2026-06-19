import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductAttributeRead(BaseModel):
    id: uuid.UUID
    key: str
    display_name: str | None
    data_type: str
    sort_order: int
    is_visible: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductAttributeCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=512)
    display_name: str | None = Field(None, max_length=512)
    data_type: str = Field("boolean", pattern="^(boolean|numeric|text)$")
    sort_order: int = Field(0, ge=0)
    is_visible: bool = True


class ProductAttributeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=512)
    data_type: str | None = Field(None, pattern="^(boolean|numeric|text)$")
    sort_order: int | None = Field(None, ge=0)
    is_visible: bool | None = None


class ProductAttributeBulkDelete(BaseModel):
    ids: list[uuid.UUID]
