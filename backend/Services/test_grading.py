from Repository import test_grading as repo

async def auto_grade_submission(*args, **kwargs):
    return await repo.auto_grade_submission(*args, **kwargs)

async def _mark_block_completed(*args, **kwargs):
    return await repo._mark_block_completed(*args, **kwargs)

__all__ = ['auto_grade_submission', '_mark_block_completed']
