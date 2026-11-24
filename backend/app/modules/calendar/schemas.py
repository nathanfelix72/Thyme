"""Calendar / Google Calendar API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoogleStatus(BaseModel):
    configured: bool
    connected: bool
    email: str | None = None
    redirect_uri: str
    can_configure: bool = True


class GoogleAppCredentialsUpdate(BaseModel):
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)


class GoogleAuthUrl(BaseModel):
    url: str


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: str
    end: str | None = None
    all_day: bool = False
    calendar_id: str | None = None
    calendar_name: str | None = None
    calendar_color: str | None = None


class WeekPlan(BaseModel):
    connected: bool
    start: str
    end: str
    email: str | None = None
    events: list[CalendarEvent] = Field(default_factory=list)
