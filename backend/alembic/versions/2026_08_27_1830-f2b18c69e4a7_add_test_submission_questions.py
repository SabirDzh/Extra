"""Persist questions assigned to each test attempt.

Revision ID: f2b18c69e4a7
Revises: b9e8d7c6a5f4
Create Date: 2026-08-27 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2b18c69e4a7"
down_revision: Union[str, None] = "b9e8d7c6a5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_submissions",
        sa.Column(
            "is_submitted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_table(
        "test_submission_questions",
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_test_submission_questions_question_id_questions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["test_submissions.id"],
            name=op.f(
                "fk_test_submission_questions_submission_id_test_submissions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "submission_id",
            "question_id",
            name=op.f("pk_test_submission_questions"),
        ),
    )


def downgrade() -> None:
    op.drop_table("test_submission_questions")
    op.drop_column("test_submissions", "is_submitted")
