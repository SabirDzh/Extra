import uuid

from pydantic import BaseModel
from utils.reference import ReferenceType


class ReferenceItemRead(BaseModel):
    id: uuid.UUID
    type: ReferenceType
    title: str
    content: str
