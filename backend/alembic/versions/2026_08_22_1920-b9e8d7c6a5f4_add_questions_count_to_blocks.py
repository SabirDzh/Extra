"""add questions_count to blocks

Revision ID: b9e8d7c6a5f4
Revises: a1b2c3d4e5f6
Create Date: 2026-08-22 19:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9e8d7c6a5f4"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "blocks",
        sa.Column("questions_count", sa.Integer(), nullable=True, default=None),
    )


def downgrade() -> None:
    op.drop_column("blocks", "questions_count")
