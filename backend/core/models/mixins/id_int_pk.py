import uuid

import uuid_utils
from sqlalchemy.orm import Mapped, mapped_column


class IdUuidPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(default=uuid_utils.uuid7, primary_key=True)
