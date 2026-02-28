import uuid
from enum import StrEnum

from pydantic import BaseModel


class SearchType(StrEnum):
    product = "product"
    course = "course"
    faq = "faq"
    term = "term"


class GlobalSearchResult(BaseModel):
    id: uuid.UUID
    type: SearchType
    title: str
    description: str | None
    relevance: float

    model_config = {"from_attributes": True}
