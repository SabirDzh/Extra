import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    id: uuid.UUID
    title: str
    image_url: list[str]

    model_config = ConfigDict(
        from_attributes=True,
    )


class ProductListRead(ProductBase):
    pass


class ProductRead(ProductBase):
    description: str
    documentation: str | None
    schema_connect: str | None
    views: int = 0
    attributes: dict[str, Any]


class ProductCreate(BaseModel):
    title: str = Field(
        ..., max_length=256
    )  # TODO validate whether a pattern should be used to restrict characters
    description: str = Field(..., max_length=2048)
    documentation: str | None = None
    schema_connect: str | None = None  # TODO consider using HttpUrl
    attributes: dict[str, Any]  # TODO add DTO inside the pydantic model
    image_url: list[str]  # TODO consider using HttpUrl

    model_config = ConfigDict(
        from_attributes=True,
    )


class ProductUpdate(BaseModel):
    title: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=2048)
    documentation: str | None = None
    schema_connect: str | None = None
    attributes: dict[str, Any] | None = None
    image_url: list[str] | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class ProductSummaryInfo(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    image_url: list[str]

    model_config = ConfigDict(
        from_attributes=True,
    )
