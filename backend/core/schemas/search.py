from pydantic import BaseModel

from core.schemas.course import CourseRead
from core.schemas.product import ProductRead
from core.schemas.term import TermResponse
from core.schemas.error import ErrorRead
from core.schemas.faq import FAQRead
from core.schemas.recommendation import RecommendationRead


class GlobalSearchResponse(BaseModel):
    courses: list[CourseRead]
    products: list[ProductRead]
    terms: list[TermResponse]
    errors: list[ErrorRead]
    faqs: list[FAQRead]
    recommendations: list[RecommendationRead]

