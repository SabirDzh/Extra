import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    documentation: (
        str | None
    )  # TODO clarify whether this stores a link or the documentation content
    schema_connect: str | None  # TODO revisit this field
    attributes: dict[str, Any]
    image_url: list[str]
    views: int = 0

    model_config = ConfigDict(
        from_attributes=True,
    )


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
        json_schema_extra={
            "example": {
                "title": "Test product",
                "description": "Description...",
                "documentation": "http://doc...",
                "schema_connect": "http://schema...",
                "attributes": {"weight": "500g", "size": "M"},
                "image_url": ["http://img..."],
            }
        },
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
