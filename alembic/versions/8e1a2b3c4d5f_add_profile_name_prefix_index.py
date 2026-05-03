"""add profile name prefix index

Revision ID: 8e1a2b3c4d5f
Revises: 2a4f6b8c9d1e
Create Date: 2026-05-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8e1a2b3c4d5f"
down_revision: Union[str, Sequence[str], None] = "2a4f6b8c9d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_profiles_name_lower_prefix "
        "ON profiles (lower(name) text_pattern_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_profiles_name_lower_prefix")
