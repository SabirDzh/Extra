from core.config import settings
from fastapi import (
    APIRouter,
    Depends,
)
from fastapi.security import HTTPBearer

from .admin import router as admin_router
from .auth import router as auth_router
from .block import router as block_router
from .certificates import router as certificate_router
from .courses import router as course_router
from .messages import router as messages_router
from .product import router as product_router
from .service import router as service_router
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
router.include_router(admin_router)
router.include_router(block_router)
router.include_router(course_router)
router.include_router(certificate_router)
router.include_router(product_router)
