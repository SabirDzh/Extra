"""reduce_userrole_to_five_values

Revision ID: a1b2c3d4e6f7
Revises: f6a1b2c3d4e5
Create Date: 2026-05-03 19:35:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e6f7"
down_revision: Union[str, None] = "f6a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole RENAME TO userrole_old;")
    op.execute(
        "CREATE TYPE userrole AS ENUM ('administrator', 'installer', 'seller', 'serviceman', 'buyer');"
    )
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole
        USING (
            CASE
                WHEN role::text = 'admin' THEN 'administrator'
                WHEN role::text = 'user' THEN 'buyer'
                WHEN role::text = 'manager' THEN 'seller'
                WHEN role::text = 'client' THEN 'buyer'
                ELSE role::text
            END
        )::userrole;
        """
    )
    op.execute("DROP TYPE userrole_old;")


def downgrade() -> None:
    op.execute("ALTER TYPE userrole RENAME TO userrole_new;")
    op.execute(
        "CREATE TYPE userrole AS ENUM ('user', 'administrator', 'manager', 'client', 'installer', 'seller', 'serviceman', 'buyer');"
    )
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole
        USING (
            CASE
                WHEN role::text = 'seller' THEN 'manager'
                WHEN role::text = 'buyer' THEN 'user'
                ELSE role::text
            END
        )::userrole;
        """
    )
    op.execute("DROP TYPE userrole_new;")
