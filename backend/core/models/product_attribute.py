from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class ProductAttribute(IdUuidPkMixin, Base):
    key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(512), nullable=True)
    data_type: Mapped[str] = mapped_column(
        String(32), default="boolean"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_product_attribute_key_trgm",
            "key",
            postgresql_using="gin",
            postgresql_ops={"key": "gin_trgm_ops"},
        ),
    )
