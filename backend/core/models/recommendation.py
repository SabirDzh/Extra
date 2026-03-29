import datetime
import uuid

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class Recommendation(IdUuidPkMixin, Base):
    title: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(default=True)

    created_by: Mapped[uuid.UUID]
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
