"""add Term

Revision ID: a668cddeb2bd
Revises: 79995f609597
Create Date: 2026-03-09 00:27:25.029700

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "a668cddeb2bd"
down_revision: Union[str, None] = "79995f609597"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "terms",
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_terms")),
        sa.UniqueConstraint("title", name=op.f("uq_terms_title")),
    )



def downgrade() -> None:

    op.drop_table("terms")

