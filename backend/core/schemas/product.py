import uuid
from typing import Annotated, Any, Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


class ProductRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    documentation: Optional[
        str
    ]  # уточнить, в кнопке документации будет храниться ссылка на документацию, или сама документация
    schema_connect: Optional[str]  # еще раз рассмотреть это поле
    attributes: dict[str, Any]
    image_url: list[str]

    model_config = ConfigDict(from_attributes=True)


# написать преобразование к строке HttpUrl для корректной работы
class ProductCreate(BaseModel):
    title: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=2048)]
    documentation: Optional[str] = None
    schema_connect: Optional[str] = None  # посмотреть, надо ли использовать HttpUrl
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
                "attributes": {"weight": "500g", "size": "M"},
                "image_url": ["http://img..."],
            }
        },
    )


class ProductUpdate(BaseModel):
    title: Annotated[Optional[str], Field(max_length=256)] = None
    description: Annotated[Optional[str], Field(max_length=2048)] = None
    documentation: Optional[str] = None
    schema_connect: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None
    image_url: Optional[list[str]] = None


class ProductFilter(BaseModel):
    equipment_type: list[str] | None = None
    purpose: list[str] | None = None
    industry: list[str] | None = None

    # Для чисел добавляем валидацию (ge=0 - больше или равно нулю)
    min_accuracy: Annotated[float | None, Field(ge=0)] = None
    max_accuracy: Annotated[float | None, Field(ge=0)] = None

    min_temp: float | None = None
    max_temp: float | None = None

    signal_type: list[str] | None = None
    ip_rating: str | None = None
    mounting: list[str] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "equipment_type": [],
                "purpose": [],
                "industry": [],
                "min_accuracy": 0,
                "max_accuracy": 0,
                "min_temp": 0,
                "max_temp": 0,
                "signal_type": [],
                "ip_rating": "",
                "mounting": [],
            }
        }
    )


class ProductFilterResponse(BaseModel):
    max_accuracy: float = 0
    min_accuracy: float = 0

    max_temp: float = 0
    min_temp: float = 0


class ProductFilterCountItemResponse(BaseModel):
    equipment_type: int = 0
    purpose: int = 0
    industry: int = 0

    accuracy: int = 0

    temp: int = 0

    signal_type: int = 0
    ip_rating: int = 0
    mounting: int = 0
