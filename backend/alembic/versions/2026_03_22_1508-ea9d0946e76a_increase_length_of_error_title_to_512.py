"""Increase length of Error title to 512

Revision ID: ea9d0946e76a
Revises: 7f55e931cc38
Create Date: 2026-03-22 15:08:11.914566

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "ea9d0946e76a"
down_revision: Union[str, None] = "7f55e931cc38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.alter_column('errors', 'title',
               existing_type=sa.VARCHAR(length=52),
               type_=sa.String(length=512),
               existing_nullable=False)



def downgrade() -> None:

    op.alter_column('errors', 'title',
               existing_type=sa.String(length=512),
               type_=sa.VARCHAR(length=52),
               existing_nullable=False)

