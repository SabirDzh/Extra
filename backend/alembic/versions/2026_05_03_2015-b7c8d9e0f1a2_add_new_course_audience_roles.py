"""add_new_course_audience_roles

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e6f7
Create Date: 2026-05-03 20:15:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE courseaudience ADD VALUE IF NOT EXISTS 'seller';")
    op.execute("ALTER TYPE courseaudience ADD VALUE IF NOT EXISTS 'serviceman';")
    op.execute("ALTER TYPE courseaudience ADD VALUE IF NOT EXISTS 'buyer';")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Downgrade is intentionally a no-op.
    pass
