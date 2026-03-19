"""fix remaining foreign key types to uuid

Revision ID: 568355d79ef3
Revises: 3d1c8f24ce89
Create Date: 2026-03-19 14:25:41.141344

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "568355d79ef3"
down_revision: Union[str, None] = "3d1c8f24ce89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Blocks
    op.execute("ALTER TABLE blocks ALTER COLUMN course_id TYPE UUID USING course_id::text::uuid")
    
    # Questions
    op.execute("ALTER TABLE questions ALTER COLUMN block_id TYPE UUID USING block_id::text::uuid")
    
    # Answer Options
    op.execute("ALTER TABLE answer_options ALTER COLUMN question_id TYPE UUID USING question_id::text::uuid")
    
    # Test Submissions
    op.execute("ALTER TABLE test_submissions ALTER COLUMN user_id TYPE UUID USING user_id::text::uuid")
    op.execute("ALTER TABLE test_submissions ALTER COLUMN block_id TYPE UUID USING block_id::text::uuid")
    op.execute("ALTER TABLE test_submissions ALTER COLUMN graded_by TYPE UUID USING graded_by::text::uuid")
    
    # Test Answers
    op.execute("ALTER TABLE test_answers ALTER COLUMN submission_id TYPE UUID USING submission_id::text::uuid")
    op.execute("ALTER TABLE test_answers ALTER COLUMN question_id TYPE UUID USING question_id::text::uuid")
    op.execute("ALTER TABLE test_answers ALTER COLUMN selected_answer_id TYPE UUID USING selected_answer_id::text::uuid")
    
    # User Block Progress (Correct table name: user_block_progresss)
    op.execute("ALTER TABLE user_block_progresss ALTER COLUMN user_id TYPE UUID USING user_id::text::uuid")
    op.execute("ALTER TABLE user_block_progresss ALTER COLUMN block_id TYPE UUID USING block_id::text::uuid")


def downgrade() -> None:
    op.execute("ALTER TABLE user_block_progresss ALTER COLUMN block_id TYPE INTEGER USING block_id::text::integer")
    op.execute("ALTER TABLE user_block_progresss ALTER COLUMN user_id TYPE INTEGER USING user_id::text::integer")
    
    op.execute("ALTER TABLE test_answers ALTER COLUMN selected_answer_id TYPE INTEGER USING selected_answer_id::text::integer")
    op.execute("ALTER TABLE test_answers ALTER COLUMN question_id TYPE INTEGER USING question_id::text::integer")
    op.execute("ALTER TABLE test_answers ALTER COLUMN submission_id TYPE INTEGER USING submission_id::text::integer")
    
    op.execute("ALTER TABLE test_submissions ALTER COLUMN graded_by TYPE INTEGER USING graded_by::text::integer")
    op.execute("ALTER TABLE test_submissions ALTER COLUMN block_id TYPE INTEGER USING block_id::text::integer")
    op.execute("ALTER TABLE test_submissions ALTER COLUMN user_id TYPE INTEGER USING user_id::text::integer")
    
    op.execute("ALTER TABLE answer_options ALTER COLUMN question_id TYPE INTEGER USING question_id::text::integer")
    op.execute("ALTER TABLE questions ALTER COLUMN block_id TYPE INTEGER USING block_id::text::integer")
    op.execute("ALTER TABLE blocks ALTER COLUMN course_id TYPE INTEGER USING course_id::text::integer")
