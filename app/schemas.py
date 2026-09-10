from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    plan: str
    concurrency_limit: int
    created_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    slug: str
    created_at: datetime


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=2, max_length=160)
    role: str = Field(default="operator", pattern=r"^(owner|admin|manager|operator|reviewer|viewer)$")


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class ProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    workspace_id: int | None = None
    platform: str = Field(default="Web", max_length=80)
    owner: str = Field(default="Unassigned", max_length=120)
    locale: str = Field(default="en-US", max_length=32)
    timezone: str = Field(default="America/New_York", max_length=80)
    start_url: HttpUrl | str = "https://example.com"
    network_label: str = Field(default="Default egress", max_length=120)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    workspace_id: int | None
    name: str
    platform: str
    owner: str
    environment: str
    locale: str
    timezone: str
    start_url: str
    network_label: str
    status: str
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    profile_id: int
    status: str
    runtime_type: str
    worker_id: str | None
    current_url: str | None
    current_title: str | None
    error: str | None
    screenshots: int
    started_at: datetime
    stopped_at: datetime | None


class PointerInput(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class TextInput(BaseModel):
    text: str = Field(max_length=2000)
