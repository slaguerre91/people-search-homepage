"""add review user uniqueness

Revision ID: 7c3d8a1e2f6b
Revises: 5f7a9c2d1e4b
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7c3d8a1e2f6b"
down_revision: Union[str, Sequence[str], None] = "5f7a9c2d1e4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "reviews",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_reviews_user_id_users",
        "reviews",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_reviews_profile_user",
        "reviews",
        ["profile_id", "user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_reviews_profile_user", "reviews", type_="unique")
    op.drop_constraint("fk_reviews_user_id_users", "reviews", type_="foreignkey")
    op.drop_column("reviews", "user_id")
