"""add image column to error

Revision ID: f393bcf35791
Revises: ea9d0946e76a
Create Date: 2026-03-22 15:31:27.809848

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "f393bcf35791"
down_revision: Union[str, None] = "ea9d0946e76a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column("errors", sa.Column("image", sa.String(), nullable=True))



def downgrade() -> None:

    op.drop_column("errors", "image")

