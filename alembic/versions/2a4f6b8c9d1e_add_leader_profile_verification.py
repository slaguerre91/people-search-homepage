"""add leader profile verification

Revision ID: 2a4f6b8c9d1e
Revises: 7c3d8a1e2f6b
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2a4f6b8c9d1e"
down_revision: Union[str, Sequence[str], None] = "7c3d8a1e2f6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    profile_columns = {column["name"] for column in inspector.get_columns("profiles")}

    if "avatar_url" not in profile_columns:
        op.add_column("profiles", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    if "is_verified" not in profile_columns:
        op.add_column(
            "profiles",
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "verification_status" not in profile_columns:
        op.add_column(
            "profiles",
            sa.Column(
                "verification_status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'unverified'"),
            ),
        )
    if "verified_at" not in profile_columns:
        op.add_column("profiles", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    if "verified_by_user_id" not in profile_columns:
        op.add_column("profiles", sa.Column("verified_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))

    profile_fks = {
        tuple(fk.get("constrained_columns", []))
        for fk in inspector.get_foreign_keys("profiles")
    }
    if ("verified_by_user_id",) not in profile_fks:
        op.create_foreign_key(
            "fk_profiles_verified_by_user_id_users",
            "profiles",
            "users",
            ["verified_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "leader_profile_verifications" not in inspector.get_table_names():
        op.create_table(
            "leader_profile_verifications",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("profile_photo_url", sa.String(length=500), nullable=False),
            sa.Column("badge_photo_url", sa.String(length=500), nullable=False),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'self_verified'"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {index["name"] for index in inspector.get_indexes("leader_profile_verifications")}
    if "idx_leader_profile_verifications_profile_id" not in indexes:
        op.create_index(
            "idx_leader_profile_verifications_profile_id",
            "leader_profile_verifications",
            ["profile_id"],
        )
    if "idx_leader_profile_verifications_user_id" not in indexes:
        op.create_index(
            "idx_leader_profile_verifications_user_id",
            "leader_profile_verifications",
            ["user_id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_leader_profile_verifications_user_id", table_name="leader_profile_verifications")
    op.drop_index("idx_leader_profile_verifications_profile_id", table_name="leader_profile_verifications")
    op.drop_table("leader_profile_verifications")
    op.drop_constraint("fk_profiles_verified_by_user_id_users", "profiles", type_="foreignkey")
    op.drop_column("profiles", "verified_by_user_id")
    op.drop_column("profiles", "verified_at")
    op.drop_column("profiles", "verification_status")
    op.drop_column("profiles", "is_verified")
    op.drop_column("profiles", "avatar_url")
