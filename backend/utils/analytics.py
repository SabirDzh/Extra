import uuid

from core.config import settings


async def increment_product_view(reds: settings.redis, product_id: uuid.UUID):
    await reds.zincrby("product:views:all_time", 1, str(product_id))
