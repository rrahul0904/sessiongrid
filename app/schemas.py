from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    platform: str = Field(default="Web", max_length=80)
    owner: str = Field(default="Unassigned", max_length=120)
    locale: str = Field(default="en-US", max_length=32)
    timezone: str = Field(default="America/New_York", max_length=80)
    start_url: HttpUrl | str = "https://example.com"
    network_label: str = Field(default="Default egress", max_length=120)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
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
    profile_id: int
    status: str
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
