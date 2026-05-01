"""add_new_user_roles

Revision ID: 9c1a2b3d4e5f
Revises: e7f8d9c0b1a2
Create Date: 2026-05-01 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "9c1a2b3d4e5f"
down_revision: Union[str, None] = "e7f8d9c0b1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'Монтажник';")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'Продавец';")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'Сервесник';")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'Покупатель';")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Downgrade is intentionally a no-op.
    pass

