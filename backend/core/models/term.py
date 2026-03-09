from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class Term(IdUuidPkMixin, Base):
    __table_args__ = (
        Index(
            "ix_term_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_term_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )

    title: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text)
