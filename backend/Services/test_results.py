from Repository import test_results as repo

async def get_test_results_for_block(*args, **kwargs):
    return await repo.get_test_results_for_block(*args, **kwargs)

__all__ = ['get_test_results_for_block']
