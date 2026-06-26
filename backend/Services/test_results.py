from Repository import test_results as repo


async def get_test_results_for_block(*args, **kwargs):
    return await repo.get_test_results_for_block(*args, **kwargs)


async def get_submission_history(*args, **kwargs):
    return await repo.get_submission_history(*args, **kwargs)


__all__ = ["get_test_results_for_block", "get_submission_history"]
