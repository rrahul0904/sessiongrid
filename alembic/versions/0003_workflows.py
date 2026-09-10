"""workflow definitions, runs and approvals

Revision ID: 0003_workflows
Revises: 0002_runtime_orchestration
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_workflows"
down_revision = "0002_runtime_orchestration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            "version",
            name="uq_workflow_definition_org_slug_version",
        ),
    )
    op.create_index(
        "ix_workflow_definitions_organization_id",
        "workflow_definitions",
        ["organization_id"],
    )
    op.create_index(
        "ix_workflow_definitions_slug",
        "workflow_definitions",
        ["slug"],
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("definition_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False),
        sa.Column("input", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["definition_id"], ["workflow_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_runs_organization_id", "workflow_runs", ["organization_id"])
    op.create_index("ix_workflow_runs_definition_id", "workflow_runs", ["definition_id"])
    op.create_index("ix_workflow_runs_profile_id", "workflow_runs", ["profile_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_index("ix_workflow_runs_created_at", "workflow_runs", ["created_at"])

    op.create_table(
        "workflow_step_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=120), nullable=False),
        sa.Column("step_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_key", name="uq_workflow_step_run_key"),
    )
    op.create_index(
        "ix_workflow_step_runs_organization_id",
        "workflow_step_runs",
        ["organization_id"],
    )
    op.create_index("ix_workflow_step_runs_run_id", "workflow_step_runs", ["run_id"])
    op.create_index("ix_workflow_step_runs_status", "workflow_step_runs", ["status"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_run_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=320), nullable=False),
        sa.Column("decided_by", sa.String(length=320), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_run_id"], ["workflow_step_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("step_run_id"),
    )
    op.create_index("ix_approvals_organization_id", "approvals", ["organization_id"])
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"])
    op.create_index("ix_approvals_step_run_id", "approvals", ["step_run_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])
    op.create_index("ix_approvals_requested_at", "approvals", ["requested_at"])


def downgrade() -> None:
    op.drop_index("ix_approvals_requested_at", table_name="approvals")
    op.drop_index("ix_approvals_status", table_name="approvals")
    op.drop_index("ix_approvals_step_run_id", table_name="approvals")
    op.drop_index("ix_approvals_run_id", table_name="approvals")
    op.drop_index("ix_approvals_organization_id", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("ix_workflow_step_runs_status", table_name="workflow_step_runs")
    op.drop_index("ix_workflow_step_runs_run_id", table_name="workflow_step_runs")
    op.drop_index("ix_workflow_step_runs_organization_id", table_name="workflow_step_runs")
    op.drop_table("workflow_step_runs")

    op.drop_index("ix_workflow_runs_created_at", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_profile_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_definition_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_organization_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_index("ix_workflow_definitions_slug", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_organization_id", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
