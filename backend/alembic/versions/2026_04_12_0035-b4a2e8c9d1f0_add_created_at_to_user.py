"""add_created_at_to_user

Revision ID: b4a2e8c9d1f0
Revises: fcb9a1b833b8
Create Date: 2026-04-12 00:35:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b4a2e8c9d1f0'
down_revision: Union[str, None] = 'fcb9a1b833b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))



def downgrade() -> None:

    op.drop_column('users', 'created_at')

