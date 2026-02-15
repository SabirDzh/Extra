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
from .messages import router as messages_router
from .profile import router as profile_router
from .product import router as product_router
from .service import router as service_router
from .tests import router as tests_router
from .users import router as users_router

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
router.include_router(block_router)
router.include_router(tests_router)
router.include_router(certificates_router)
router.include_router(profile_router)
