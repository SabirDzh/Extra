import uuid
from typing import Literal

from pydantic import BaseModel


class OpenQuestionReview(BaseModel):
    submission_id: uuid.UUID
    status: Literal["approved", "rejected"]
    comment: str | None = None
