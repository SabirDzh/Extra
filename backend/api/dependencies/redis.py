from redis.asyncio import Redis, ConnectionPool
from core.config import settings



redis_pool = ConnectionPool(
    host=settings.redis.host,
    port=settings.redis.port,
    db=settings.redis.db.cache,
    decode_responses=True,
)

async def get_redis() -> Redis:
    """Dependency для получения клиента Redis в контроллерах."""
    return Redis(connection_pool=redis_pool)
