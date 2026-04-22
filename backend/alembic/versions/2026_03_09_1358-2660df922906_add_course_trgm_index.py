"""add course trgm index

Revision ID: 2660df922906
Revises: a668cddeb2bd
Create Date: 2026-03-09 13:58:10.256380

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "2660df922906"
down_revision: Union[str, None] = "a668cddeb2bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.create_index(
        "ix_course_description_trgm",
        "courses",
        ["description"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_course_title_trgm",
        "courses",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )



def downgrade() -> None:

    op.drop_index(
        "ix_course_title_trgm",
        table_name="courses",
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.drop_index(
        "ix_course_description_trgm",
        table_name="courses",
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )

