"""empty message

Revision ID: 365df826a665
Revises: 843d702627fa
Create Date: 2026-04-08 18:20:03.633873

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "365df826a665"
down_revision: Union[str, None] = "843d702627fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE blocktype ADD VALUE 'mixed_test'")


def downgrade() -> None:

    pass

