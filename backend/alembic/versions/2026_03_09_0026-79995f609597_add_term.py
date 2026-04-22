"""add Term

Revision ID: 79995f609597
Revises: 91ee7c608f29
Create Date: 2026-03-09 00:26:47.597698

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "79995f609597"
down_revision: Union[str, None] = "91ee7c608f29"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    pass



def downgrade() -> None:

    pass

