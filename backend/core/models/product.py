from datetime import datetime
from typing import Any

from sqlalchemy import Computed, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class Product(IdUuidPkMixin, Base):
    title: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(String(1024))
    image_url: Mapped[list[dict]] = mapped_column(
        JSONB,
        default=list,
    )  # TODO revisit: JSONB is used to store multiple images

    schema_connect: Mapped[str] = mapped_column(
        String,
        nullable=True,
    )  # TODO revisit naming/storage format; kept as-is for tests
    documentation: Mapped[str] = mapped_column(
        String,
        nullable=True,
    )  # TODO consider moving attributes into JSONB

    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    search_product: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('russian', coalesce(title,'') || ' ' || coalesce(description,''))",
            persisted=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("idx_search_product", "search_product", postgresql_using="gin"),
        Index(
            "idx_product_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )
