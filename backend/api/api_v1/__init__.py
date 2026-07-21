from core.config import settings
from fastapi import (
    APIRouter,
    Depends,
)
from fastapi.security import HTTPBearer

from .auth import router as auth_router
from .block import router as block_router
from .certificates import router as certificates_router
from .course import router as course_router
from .error import router as error_router
from .faq import router as faq_router
from .messages import router as messages_router
from .product import router as product_router
from .product_attribute import router as product_attribute_router
from .profile import router as profile_router
from .recomendation import router as recommendations_router
from .search import router as search_router
from .service import router as service_router
from .term import router as term_router
from .tests import router as tests_router
from .users import router as users_router
from .notifications import router as notifications_router
from .backups import router as backups_router

http_bearer = HTTPBearer(auto_error=False)

router = APIRouter(
    prefix=settings.api.v1.prefix,
    dependencies=[Depends(http_bearer)],
)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(messages_router)
router.include_router(service_router)
router.include_router(product_router)
router.include_router(course_router)
router.include_router(faq_router)
router.include_router(block_router)
router.include_router(tests_router)
router.include_router(certificates_router)
router.include_router(profile_router)
router.include_router(term_router)
router.include_router(search_router)
router.include_router(error_router)
router.include_router(recommendations_router)
router.include_router(notifications_router)
router.include_router(product_attribute_router)
router.include_router(backups_router)
