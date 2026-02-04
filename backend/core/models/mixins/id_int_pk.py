from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
import uuid
import uuid_utils


class IdUuidPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(default=uuid_utils.uuid7, primary_key=True)
