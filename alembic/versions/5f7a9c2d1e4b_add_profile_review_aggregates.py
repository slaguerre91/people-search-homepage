"""add profile review aggregates

Revision ID: 5f7a9c2d1e4b
Revises: 99bc1fcc52eb
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f7a9c2d1e4b"
down_revision: Union[str, Sequence[str], None] = "99bc1fcc52eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "profiles",
        sa.Column(
            "total_review_score",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "review_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.execute(
        """
        UPDATE profiles
        SET
            total_review_score = COALESCE(review_totals.total_review_score, 0),
            review_count = COALESCE(review_totals.review_count, 0)
        FROM (
            SELECT
                profile_id,
                SUM(rating)::integer AS total_review_score,
                COUNT(*)::integer AS review_count
            FROM reviews
            GROUP BY profile_id
        ) AS review_totals
        WHERE profiles.id = review_totals.profile_id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("profiles", "review_count")
    op.drop_column("profiles", "total_review_score")
