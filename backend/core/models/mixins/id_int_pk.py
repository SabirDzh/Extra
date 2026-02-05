import uuid

import uuid_utils
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column


class IdUuidPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        default=uuid_utils.uuid7,
        primary_key=True,
    )
