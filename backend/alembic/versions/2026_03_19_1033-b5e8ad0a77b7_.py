"""empty message

Revision ID: b5e8ad0a77b7
Revises: e57baf2f78e7
Create Date: 2026-03-19 10:33:04.694878

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b5e8ad0a77b7"
down_revision: Union[str, None] = "e57baf2f78e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:

    pass

