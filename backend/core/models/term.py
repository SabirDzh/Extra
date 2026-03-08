from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class Term(IdUuidPkMixin, Base):
    title: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text)
