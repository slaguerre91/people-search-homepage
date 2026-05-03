"""add profile linkedin url

Revision ID: 1f2e3d4c5b6a
Revises: 8e1a2b3c4d5f
Create Date: 2026-05-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f2e3d4c5b6a"
down_revision: Union[str, Sequence[str], None] = "8e1a2b3c4d5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    profile_columns = {column["name"] for column in inspector.get_columns("profiles")}

    if "linkedin_url" not in profile_columns:
        op.add_column("profiles", sa.Column("linkedin_url", sa.String(length=500), nullable=True))

    op.execute(
        """
        UPDATE profiles
        SET linkedin_url = lower(
            'https://www.linkedin.com/in/' ||
            substring(bio from 'linkedin\\.com/in/([^/?#[:space:]]+)')
        )
        WHERE linkedin_url IS NULL
          AND bio ~* 'linkedin\\.com/in/[^/?#[:space:]]+'
        """
    )
    op.execute(
        """
        WITH ranked_profiles AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY linkedin_url
                    ORDER BY created_at ASC NULLS LAST, id ASC
                ) AS row_number
            FROM profiles
            WHERE linkedin_url IS NOT NULL
        )
        UPDATE profiles
        SET linkedin_url = NULL
        FROM ranked_profiles
        WHERE profiles.id = ranked_profiles.id
          AND ranked_profiles.row_number > 1
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_linkedin_url "
        "ON profiles (linkedin_url) "
        "WHERE linkedin_url IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_profiles_linkedin_url")
    op.drop_column("profiles", "linkedin_url")
