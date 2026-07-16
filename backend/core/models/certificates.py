import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class Certificate(IdUuidPkMixin, Base):
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    certificate_number: Mapped[str] = mapped_column(
        String(36), unique=True, default=lambda: str(uuid.uuid4())
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User", back_populates="certificates")
    course = relationship("Course", back_populates="certificates")
