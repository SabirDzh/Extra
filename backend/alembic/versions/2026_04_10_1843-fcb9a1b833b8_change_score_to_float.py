"""change score to float

Revision ID: fcb9a1b833b8
Revises: 365df826a665
Create Date: 2026-04-10 18:43:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "fcb9a1b833b8"
down_revision: Union[str, None] = "365df826a665"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.alter_column('test_submissions', 'score',
               existing_type=sa.INTEGER(),
               type_=sa.Float(),
               existing_nullable=True)
    op.alter_column('test_submissions', 'max_score',
               existing_type=sa.INTEGER(),
               type_=sa.Float(),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('test_submissions', 'max_score',
               existing_type=sa.Float(),
               type_=sa.INTEGER(),
               existing_nullable=False)
    op.alter_column('test_submissions', 'score',
               existing_type=sa.Float(),
               type_=sa.INTEGER(),
               existing_nullable=True)
