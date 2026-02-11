"""add created_by to courses

Revision ID: 7a1c0b2d3e4f
Revises: df1f06ae3d55
Create Date: 2026-02-11 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7a1c0b2d3e4f"
down_revision: Union[str, None] = "a3c1f2d4e6b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("courses")}
    if "created_by" not in columns:
        op.add_column(
            "courses",
            sa.Column("created_by", sa.UUID(), nullable=True),
        )

        op.create_foreign_key(
            "fk_courses_created_by_users",
            "courses",
            "users",
            ["created_by"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    fks = inspector.get_foreign_keys("courses")
    fk_names = {fk.get("name") for fk in fks}
    if "fk_courses_created_by_users" in fk_names:
        op.drop_constraint("fk_courses_created_by_users", "courses", type_="foreignkey")

    columns = {col["name"] for col in inspector.get_columns("courses")}
    if "created_by" in columns:
        op.drop_column("courses", "created_by")
