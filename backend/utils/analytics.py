import uuid

from redis.asyncio import Redis


async def increment_product_view(redis: Redis, product_id: uuid.UUID):
    await redis.zincrby("product:views:all_time", 1, str(product_id))
