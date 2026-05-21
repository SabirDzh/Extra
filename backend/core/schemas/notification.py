import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from Domain.Enums.notification import NotificationType

class NotificationBase(BaseModel):
    title: str = Field(..., description="Short title of the notification")
    message: str = Field(..., description="Detailed message")
    type: NotificationType
    reference_id: uuid.UUID | None = None

class NotificationRead(NotificationBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    is_read: bool
