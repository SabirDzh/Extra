"""add course level and fix enrollment types

Revision ID: a320c8d96f01
Revises: 8f84b9681a4c
Create Date: 2026-03-19 13:14:05.938005

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a320c8d96f01"
down_revision: Union[str, None] = "8f84b9681a4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for courselevel
    course_level = postgresql.ENUM('beginner', 'intermediate', 'advanced', name='courselevel')
    course_level.create(op.get_bind())

    # Add level column to courses
    op.add_column(
        "courses",
        sa.Column(
            "level",
            sa.Enum("beginner", "intermediate", "advanced", name="courselevel"),
            nullable=False,
            server_default="beginner"
        ),
    )
    
    # Fix CourseEnrollment types (int -> uuid)
    # We need to drop the constraints first, change types, and then recreate them if necessary
    # But since these are foreign keys, simpler to just alter with USING clause
    op.execute("ALTER TABLE course_enrollments ALTER COLUMN user_id TYPE UUID USING user_id::text::uuid")
    op.execute("ALTER TABLE course_enrollments ALTER COLUMN course_id TYPE UUID USING course_id::text::uuid")


def downgrade() -> None:
    # Revert CourseEnrollment types (uuid -> int)
    op.execute("ALTER TABLE course_enrollments ALTER COLUMN user_id TYPE INTEGER USING user_id::text::integer")
    op.execute("ALTER TABLE course_enrollments ALTER COLUMN course_id TYPE INTEGER USING course_id::text::integer")

    # Drop level column
    op.drop_column("courses", "level")
    
    # Drop enum type
    sa.Enum(name="courselevel").drop(op.get_bind())
