from core.config import settings
from fastapi import APIRouter

router = APIRouter(
    prefix=settings.api.v1.blocks,
    tags=["Blocks"],
)


@router.get("/{block_id}")
async def get_block():
    pass


@router.post("/{block_id}/watch")
async def watch_block():
    pass


@router.get("/{block_id}/test")
async def get_test_block():
    pass


@router.post("/{block_id}/test/submit")
async def check_test():
    pass


@router.get("/{block_id}/test/attempts")
async def attempts_history():
    pass
