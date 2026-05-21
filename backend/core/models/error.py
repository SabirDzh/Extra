import datetime
import uuid

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class Error(IdUuidPkMixin, Base):
    title: Mapped[str] = mapped_column(String(512), unique=True)
    description: Mapped[str] = mapped_column(String(16384))
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    order_index: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[uuid.UUID]
