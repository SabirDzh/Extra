"""rename_user_roles_to_english

Revision ID: f6a1b2c3d4e5
Revises: c3f7a1d9e2b4
Create Date: 2026-05-03 19:05:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "f6a1b2c3d4e5"
down_revision: Union[str, None] = "c3f7a1d9e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename_enum_value_if_exists(old_value: str, new_value: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'userrole' AND e.enumlabel = '{old_value}'
            ) THEN
                ALTER TYPE userrole RENAME VALUE '{old_value}' TO '{new_value}';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    _rename_enum_value_if_exists("Монтажник", "installer")
    _rename_enum_value_if_exists("Продавец", "seller")
    _rename_enum_value_if_exists("Сервесник", "serviceman")
    _rename_enum_value_if_exists("Покупатель", "buyer")


def downgrade() -> None:
    _rename_enum_value_if_exists("installer", "Монтажник")
    _rename_enum_value_if_exists("seller", "Продавец")
    _rename_enum_value_if_exists("serviceman", "Сервесник")
    _rename_enum_value_if_exists("buyer", "Покупатель")
