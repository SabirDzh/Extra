from pydantic import BaseModel

from core.schemas.course import CourseRead
from core.schemas.product import ProductRead
from core.schemas.term import TermResponse


class GlobalSearchResponse(BaseModel):
    courses: list[CourseRead]
    products: list[ProductRead]
    terms: list[TermResponse]
