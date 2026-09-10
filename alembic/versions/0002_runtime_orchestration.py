"""runtime orchestration and artifact persistence

Revision ID: 0002_runtime_orchestration
Revises: 0001_control_plane
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_runtime_orchestration"
down_revision = "0001_control_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_workers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_key", sa.String(length=120), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("capabilities", sa.Text(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_key"),
    )
    op.create_index("ix_runtime_workers_worker_key", "runtime_workers", ["worker_key"])
    op.create_index("ix_runtime_workers_last_heartbeat_at", "runtime_workers", ["last_heartbeat_at"])

    op.create_table(
        "runtime_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["browser_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runtime_tasks_organization_id", "runtime_tasks", ["organization_id"])
    op.create_index("ix_runtime_tasks_profile_id", "runtime_tasks", ["profile_id"])
    op.create_index("ix_runtime_tasks_session_id", "runtime_tasks", ["session_id"])
    op.create_index("ix_runtime_tasks_task_type", "runtime_tasks", ["task_type"])
    op.create_index("ix_runtime_tasks_status", "runtime_tasks", ["status"])
    op.create_index("ix_runtime_tasks_available_at", "runtime_tasks", ["available_at"])
    op.create_index("ix_runtime_tasks_created_at", "runtime_tasks", ["created_at"])

    op.create_table(
        "runtime_leases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["browser_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["runtime_workers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_runtime_leases_organization_id", "runtime_leases", ["organization_id"])
    op.create_index("ix_runtime_leases_profile_id", "runtime_leases", ["profile_id"])
    op.create_index("ix_runtime_leases_session_id", "runtime_leases", ["session_id"])
    op.create_index("ix_runtime_leases_worker_id", "runtime_leases", ["worker_id"])
    op.create_index("ix_runtime_leases_status", "runtime_leases", ["status"])
    op.create_index("ix_runtime_leases_expires_at", "runtime_leases", ["expires_at"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["browser_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_artifacts_organization_id", "artifacts", ["organization_id"])
    op.create_index("ix_artifacts_profile_id", "artifacts", ["profile_id"])
    op.create_index("ix_artifacts_session_id", "artifacts", ["session_id"])
    op.create_index("ix_artifacts_kind", "artifacts", ["kind"])
    op.create_index("ix_artifacts_sha256", "artifacts", ["sha256"])
    op.create_index("ix_artifacts_created_at", "artifacts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_artifacts_created_at", table_name="artifacts")
    op.drop_index("ix_artifacts_sha256", table_name="artifacts")
    op.drop_index("ix_artifacts_kind", table_name="artifacts")
    op.drop_index("ix_artifacts_session_id", table_name="artifacts")
    op.drop_index("ix_artifacts_profile_id", table_name="artifacts")
    op.drop_index("ix_artifacts_organization_id", table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index("ix_runtime_leases_expires_at", table_name="runtime_leases")
    op.drop_index("ix_runtime_leases_status", table_name="runtime_leases")
    op.drop_index("ix_runtime_leases_worker_id", table_name="runtime_leases")
    op.drop_index("ix_runtime_leases_session_id", table_name="runtime_leases")
    op.drop_index("ix_runtime_leases_profile_id", table_name="runtime_leases")
    op.drop_index("ix_runtime_leases_organization_id", table_name="runtime_leases")
    op.drop_table("runtime_leases")

    op.drop_index("ix_runtime_tasks_created_at", table_name="runtime_tasks")
    op.drop_index("ix_runtime_tasks_available_at", table_name="runtime_tasks")
    op.drop_index("ix_runtime_tasks_status", table_name="runtime_tasks")
    op.drop_index("ix_runtime_tasks_task_type", table_name="runtime_tasks")
    op.drop_index("ix_runtime_tasks_session_id", table_name="runtime_tasks")
    op.drop_index("ix_runtime_tasks_profile_id", table_name="runtime_tasks")
    op.drop_index("ix_runtime_tasks_organization_id", table_name="runtime_tasks")
    op.drop_table("runtime_tasks")

    op.drop_index("ix_runtime_workers_last_heartbeat_at", table_name="runtime_workers")
    op.drop_index("ix_runtime_workers_worker_key", table_name="runtime_workers")
    op.drop_table("runtime_workers")
