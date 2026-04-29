from Repository import search as repo

async def global_search_entities(*args, **kwargs):
    return await repo.global_search_entities(*args, **kwargs)

__all__ = ['global_search_entities']
