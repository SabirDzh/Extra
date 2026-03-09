import uuid
from redis.asyncio import Redis

async def track_product_view(redis: Redis, product_id: uuid.UUID, user_identifier: str):
    """
    Tracks a unique view for a product using HyperLogLog and updates 
    a global popularity leaderboard (ZSET).
    """
    hll_key = f"product:{product_id}:unique_views"
    leaderboard_key = "products:popularity"
    
    # PFADD returns 1 if at least one element was added (new unique view)
    is_new = await redis.pfadd(hll_key, user_identifier)
    
    if is_new:
        # Increment score in the global leaderboard
        await redis.zincrby(leaderboard_key, 1, str(product_id))

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

async def get_top_product_ids(redis: Redis, limit: int = 10, offset: int = 0) -> list[str]:
    """Returns product IDs sorted by popularity (unique views) from Redis."""
    leaderboard_key = "products:popularity"
    # ZREVRANGE returns elements from highest to lowest score
    return await redis.zrevrange(leaderboard_key, offset, offset + limit - 1)
