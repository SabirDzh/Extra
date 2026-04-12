from pydantic import BaseModel


class StatMetric(BaseModel):
    count: int
    percent: float


class AdminSummaryRead(BaseModel):
    total_users: int
    total_tests_passed: int
    course_stats: StatMetric
    new_users_stats: StatMetric
