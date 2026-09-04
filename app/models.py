from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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

    sessions: Mapped[list["BrowserSession"]] = relationship(back_populates="profile")


class BrowserSession(Base):
    __tablename__ = "browser_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="starting")
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
    actor: Mapped[str] = mapped_column(String(120), default="local-operator")
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
