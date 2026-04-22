"""use text type for product fields

Revision ID: 8f84b9681a4c
Revises: b5e8ad0a77b7
Create Date: 2026-03-19 10:38:45.543593

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8f84b9681a4c"
down_revision: Union[str, None] = "b5e8ad0a77b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.execute("DROP INDEX IF EXISTS idx_search_product")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS search_product")


    op.alter_column(
        "products",
        "schema_connect",
        existing_type=sa.VARCHAR(),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "documentation",
        existing_type=sa.VARCHAR(),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.execute("ALTER TABLE products ALTER COLUMN description TYPE TEXT")


    op.execute(
        """
        ALTER TABLE products ADD COLUMN search_product tsvector
        GENERATED ALWAYS AS (
            to_tsvector('russian', coalesce(title, '') || ' ' || coalesce(description, ''))
        ) STORED
        """
    )


    op.create_index(
        "idx_search_product",
        "products",
        ["search_product"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_search_product", table_name="products", postgresql_using="gin"
    )
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS search_product")
    
    op.execute(
        """
        ALTER TABLE products ADD COLUMN search_product tsvector
        GENERATED ALWAYS AS (
            to_tsvector('russian', description)
        ) STORED
        """
    )
    
    op.alter_column(
        "products",
        "documentation",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "schema_connect",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(),
        existing_nullable=True,
    )
