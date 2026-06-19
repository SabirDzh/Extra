"""add product_attributes table

Revision ID: a1b2c3d4e5f6
Revises: c828a1305293
Create Date: 2026-06-19 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c828a1305293"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_attributes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=True),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_attributes")),
    )
    op.create_index(
        op.f("ix_product_attributes_key"),
        "product_attributes",
        ["key"],
        unique=True,
    )
    op.create_index(
        "ix_product_attribute_key_trgm",
        "product_attributes",
        ["key"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"key": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_attribute_key_trgm",
        table_name="product_attributes",
        postgresql_using="gin",
        postgresql_ops={"key": "gin_trgm_ops"},
    )
    op.drop_index(
        op.f("ix_product_attributes_key"),
        table_name="product_attributes",
    )
    op.drop_table("product_attributes")
