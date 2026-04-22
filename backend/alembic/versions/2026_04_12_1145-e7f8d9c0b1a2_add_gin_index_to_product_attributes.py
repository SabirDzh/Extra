"""add_gin_index_to_product_attributes

Revision ID: e7f8d9c0b1a2
Revises: b4a2e8c9d1f0
Create Date: 2026-04-12 11:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e7f8d9c0b1a2'
down_revision: Union[str, None] = 'b4a2e8c9d1f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_index('idx_product_attributes_gin', 'products', ['attributes'], unique=False, postgresql_using='gin')



def downgrade() -> None:

    op.drop_index('idx_product_attributes_gin', table_name='products', postgresql_using='gin')

