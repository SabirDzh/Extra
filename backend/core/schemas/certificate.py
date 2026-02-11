import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CertificateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    certificate_number: str
    issued_at: datetime

    model_config = ConfigDict(from_attributes=True)
