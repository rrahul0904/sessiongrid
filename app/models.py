from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(40), default="development")
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="workspaces")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(20), index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    platform: Mapped[str] = mapped_column(String(80), default="Web")
    owner: Mapped[str] = mapped_column(String(120), default="Unassigned")
    environment: Mapped[str] = mapped_column(String(40), default="browser")
    locale: Mapped[str] = mapped_column(String(32), default="en-US")
    timezone: Mapped[str] = mapped_column(String(80), default="America/New_York")
    start_url: Mapped[str] = mapped_column(String(2048), default="https://example.com")
    network_label: Mapped[str] = mapped_column(String(120), default="Default egress")
    status: Mapped[str] = mapped_column(String(32), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list["BrowserSession"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class BrowserSession(Base):
    __tablename__ = "browser_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="starting")
    runtime_type: Mapped[str] = mapped_column(String(40), default="browser")
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    current_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshots: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="sessions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("browser_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(80), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RuntimeWorker(Base):
    __tablename__ = "runtime_workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    region: Mapped[str] = mapped_column(String(80), default="local")
    status: Mapped[str] = mapped_column(String(32), default="online")
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    capabilities: Mapped[str] = mapped_column(Text, default='["browser"]')
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RuntimeTask(Base):
    __tablename__ = "runtime_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("browser_sessions.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RuntimeLease(Base):
    __tablename__ = "runtime_leases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("browser_sessions.id", ondelete="CASCADE"), unique=True, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("runtime_workers.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("browser_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", "version", name="uq_workflow_definition_org_slug_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    definition: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    definition_id: Mapped[int] = mapped_column(ForeignKey("workflow_definitions.id", ondelete="RESTRICT"), index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowStepRun(Base):
    __tablename__ = "workflow_step_runs"
    __table_args__ = (UniqueConstraint("run_id", "step_key", name="uq_workflow_step_run_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    step_key: Mapped[str] = mapped_column(String(120))
    step_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    step_run_id: Mapped[int] = mapped_column(ForeignKey("workflow_step_runs.id", ondelete="CASCADE"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    prompt: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(320))
    decided_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
