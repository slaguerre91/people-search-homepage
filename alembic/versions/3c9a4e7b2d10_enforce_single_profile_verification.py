"""enforce single profile verification

Revision ID: 3c9a4e7b2d10
Revises: 1f2e3d4c5b6a
Create Date: 2026-05-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3c9a4e7b2d10"
down_revision: Union[str, Sequence[str], None] = "1f2e3d4c5b6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DELETE FROM leader_profile_verifications
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY profile_id
                        ORDER BY created_at ASC NULLS LAST
                    ) AS row_number
                FROM leader_profile_verifications
            ) ranked
            WHERE row_number > 1
        )
        """
    )
    op.execute(
        """
        DELETE FROM leader_profile_verifications
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id
                        ORDER BY created_at ASC NULLS LAST
                    ) AS row_number
                FROM leader_profile_verifications
            ) ranked
            WHERE row_number > 1
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_leader_profile_verifications_profile_id "
        "ON leader_profile_verifications (profile_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_leader_profile_verifications_user_id "
        "ON leader_profile_verifications (user_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_profiles_verified_by_user_id "
        "ON profiles (verified_by_user_id) WHERE verified_by_user_id IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS uq_profiles_verified_by_user_id")
    op.execute("DROP INDEX IF EXISTS uq_leader_profile_verifications_user_id")
    op.execute("DROP INDEX IF EXISTS uq_leader_profile_verifications_profile_id")
