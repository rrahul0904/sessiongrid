"""baseline multi-tenant control plane

Revision ID: 0001_control_plane
Revises:
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_control_plane"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("plan", sa.String(length=40), nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_hash"),
    )
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_secret_hash", "api_keys", ["secret_hash"])

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=False),
        sa.Column("environment", sa.String(length=40), nullable=False),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("start_url", sa.String(length=2048), nullable=False),
        sa.Column("network_label", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profiles_organization_id", "profiles", ["organization_id"])
    op.create_index("ix_profiles_workspace_id", "profiles", ["workspace_id"])
    op.create_index("ix_profiles_name", "profiles", ["name"])

    op.create_table(
        "browser_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("runtime_type", sa.String(length=40), nullable=False),
        sa.Column("worker_id", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("current_url", sa.String(length=2048), nullable=True),
        sa.Column("current_title", sa.String(length=512), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("screenshots", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_browser_sessions_organization_id", "browser_sessions", ["organization_id"])
    op.create_index("ix_browser_sessions_profile_id", "browser_sessions", ["profile_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=320), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("metric", sa.String(length=80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["browser_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usage_events_organization_id", "usage_events", ["organization_id"])
    op.create_index("ix_usage_events_session_id", "usage_events", ["session_id"])
    op.create_index("ix_usage_events_metric", "usage_events", ["metric"])
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_metric", table_name="usage_events")
    op.drop_index("ix_usage_events_session_id", table_name="usage_events")
    op.drop_index("ix_usage_events_organization_id", table_name="usage_events")
    op.drop_table("usage_events")

    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_browser_sessions_profile_id", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_organization_id", table_name="browser_sessions")
    op.drop_table("browser_sessions")

    op.drop_index("ix_profiles_name", table_name="profiles")
    op.drop_index("ix_profiles_workspace_id", table_name="profiles")
    op.drop_index("ix_profiles_organization_id", table_name="profiles")
    op.drop_table("profiles")

    op.drop_index("ix_api_keys_secret_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_api_keys_organization_id", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_organization_id", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
