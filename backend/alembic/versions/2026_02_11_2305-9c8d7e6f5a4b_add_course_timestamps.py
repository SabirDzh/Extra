"""add course timestamps

Revision ID: 9c8d7e6f5a4b
Revises: 7a1c0b2d3e4f
Create Date: 2026-02-11 23:05:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9c8d7e6f5a4b"
down_revision: Union[str, None] = "7a1c0b2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_non_null_now_column_if_missing(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}

    if column_name in columns:
        return

    op.add_column(
        table_name,
        sa.Column(
            column_name,
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            f"UPDATE {table_name} SET {column_name} = now() WHERE {column_name} IS NULL"
        )
    )

    op.alter_column(table_name, column_name, nullable=False)


def upgrade() -> None:
    _add_non_null_now_column_if_missing("courses", "created_at")
    _add_non_null_now_column_if_missing("courses", "updated_at")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("courses")}

    if "updated_at" in columns:
        op.drop_column("courses", "updated_at")
    if "created_at" in columns:
        op.drop_column("courses", "created_at")
