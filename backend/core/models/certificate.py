import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.reference import ReferenceType

from core.models.base import Base
from core.models.mixins.id_int_pk import IdUuidPkMixin
from core.models.user import User


class Certificate(IdUuidPkMixin, Base):
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"))

    certificate_number: Mapped[str] = mapped_column(unique=True)
    issue_date: Mapped[datetime] = mapped_column(default=func.now())

    pdf_url: Mapped[str] = mapped_column(String)

    user: Mapped["User"] = relationship(back_populates="certificates")


class ReferenceItem(IdUuidPkMixin, Base):
    type: Mapped[ReferenceType] = mapped_column()
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)

    keywords: Mapped[str | None] = mapped_column(String)
