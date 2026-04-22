"""add_course_audience_field

Revision ID: 843d702627fa
Revises: d2f18f30147d
Create Date: 2026-04-06 00:04:53.516583

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "843d702627fa"
down_revision: Union[str, None] = "d2f18f30147d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    courseaudience = sa.Enum("everyone", "installer", name="courseaudience")
    courseaudience.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "courses",
        sa.Column(
            "audience",
            courseaudience,
            nullable=False,
            server_default="everyone",
        ),
    )

    op.alter_column("courses", "audience", server_default=None)


def downgrade() -> None:
    op.drop_column("courses", "audience")
    sa.Enum(name="courseaudience").drop(op.get_bind(), checkfirst=True)
