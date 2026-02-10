import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    documentation: (
        str | None
    )  # уточнить, в кнопке документации будет храниться ссылка на документацию, или сама документация
    schema_connect: str | None  # еще раз рассмотреть это поле
    attributes: dict[str, Any]
    image_url: list[str]


class ProductCreate(BaseModel):
    title: str = Field(
        ..., max_length=256
    )  # проверить возможность указания паттерна для исключения лишних символов
    description: str = Field(..., max_length=2048)
    documentation: str | None = None
    schema_connect: str | None = None  # посмотреть, надо ли использовать HttpUrl
    attributes: dict[str, Any]  # добавить DTO внутрь pydantic модели
    image_url: list[str]  # посмотреть, надо ли использовать HttpUrl

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "title": "Тестовый товар",
                "description": "Описание...",
                "documentation": "http://doc...",
                "schema_connect": "http://schema...",
                "attributes": {"price": 1000, "weight": "500g", "size": "M"},
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
