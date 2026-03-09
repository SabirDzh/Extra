import uuid
from redis.asyncio import Redis

async def track_product_view(redis: Redis, product_id: uuid.UUID, user_identifier: str):
    """
    Tracks a unique view for a product using HyperLogLog.
    user_identifier can be a user_id or IP address.
    """
    key = f"product:{product_id}:unique_views"
    await redis.pfadd(key, user_identifier)

async def get_product_views(redis: Redis, product_id: uuid.UUID) -> int:
    """Returns the approximate unique view count for a product."""
    key = f"product:{product_id}:unique_views"
    return await redis.pfcount(key)

async def get_multiple_product_views(redis: Redis, product_ids: list[uuid.UUID]) -> list[int]:
    """Returns unique view counts for multiple products efficiently using a pipeline."""
    if not product_ids:
        return []
        
    pipeline = redis.pipeline()
    for pid in product_ids:
        key = f"product:{pid}:unique_views"
        pipeline.pfcount(key)
        
    return await pipeline.execute()
