from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base

from .mixins.id_int_pk import IdUuidPkMixin


class UserBlockProgress(IdUuidPkMixin, Base):
    __table_args__ = (UniqueConstraint("user_id", "block_id", name="uq_user_block"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    block_id: Mapped[int] = mapped_column(ForeignKey("blocks.id"))
    is_completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User", back_populates="block_progress")
    block = relationship("Block", back_populates="progress_records")
