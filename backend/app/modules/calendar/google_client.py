"""Google Calendar OAuth + events helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.modules.calendar.app_credentials import (
    GoogleAppCredentials,
    resolve_credentials,
)
from app.modules.shared import config

CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_LIST_URL = (
    "https://www.googleapis.com/calendar/v3/users/me/calendarList"
)
GOOGLE_PRIMARY_CAL_URL = "https://www.googleapis.com/calendar/v3/calendars/primary"


def get_credentials() -> GoogleAppCredentials | None:
    return resolve_credentials()


def google_configured() -> bool:
    return get_credentials() is not None


def redirect_uri() -> str:
    return config.GOOGLE_REDIRECT_URI


def build_auth_url(state: str) -> str:
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Google OAuth is not configured")
    params = {
        "client_id": creds.client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": CALENDAR_READONLY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    """Exchange authorization code for tokens. Returns token response dict."""
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Google OAuth is not configured")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Google token exchange failed: {resp.text}")
        return resp.json()


def refresh_access_token(refresh_token: str) -> str:
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Google OAuth is not configured")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Google token refresh failed: {resp.text}")
        data = resp.json()
        access = data.get("access_token")
        if not access:
            raise RuntimeError("Google token refresh returned no access_token")
        return str(access)


def fetch_user_email(access_token: str) -> str | None:
    """Primary calendar id is usually the account email."""
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(
            GOOGLE_PRIMARY_CAL_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code >= 400:
            return None
        cal_id = resp.json().get("id")
        return str(cal_id) if cal_id else None


def week_bounds(start: date | None = None) -> tuple[date, date]:
    """Return [week_start, week_end) as dates. Week starts Sunday."""
    anchor = start or date.today()
    # Python weekday: Mon=0 … Sun=6 → days since Sunday
    week_start = anchor - timedelta(days=(anchor.weekday() + 1) % 7)
    week_end = week_start + timedelta(days=7)
    return week_start, week_end


def _events_url(calendar_id: str) -> str:
    return (
        "https://www.googleapis.com/calendar/v3/calendars/"
        f"{quote(calendar_id, safe='')}/events"
    )


def _list_calendars(client: httpx.Client, access_token: str) -> list[dict[str, Any]]:
    calendars: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        params: dict[str, str] = {"maxResults": "250", "minAccessRole": "reader"}
        if page_token:
            params["pageToken"] = page_token
        resp = client.get(
            GOOGLE_CALENDAR_LIST_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Google calendarList.list failed: {resp.text}")
        data = resp.json()
        for item in data.get("items") or []:
            # Match Google Calendar UI: only calendars the user has selected/visible.
            if item.get("selected") is False:
                continue
            cal_id = item.get("id")
            if not cal_id:
                continue
            calendars.append(
                {
                    "id": str(cal_id),
                    "summary": str(
                        item.get("summaryOverride")
                        or item.get("summary")
                        or cal_id
                    ),
                    "color": item.get("backgroundColor") or item.get("colorId"),
                    "primary": bool(item.get("primary")),
                }
            )
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    if not calendars:
        calendars.append(
            {
                "id": "primary",
                "summary": "Primary",
                "color": None,
                "primary": True,
            }
        )
    return calendars


def _parse_event(
    item: dict[str, Any],
    *,
    calendar_id: str,
    calendar_name: str,
    calendar_color: str | None,
) -> dict[str, Any] | None:
    event_id = item.get("id")
    if not event_id:
        return None
    start_obj = item.get("start") or {}
    end_obj = item.get("end") or {}
    base = {
        "id": f"{calendar_id}:{event_id}",
        "title": str(item.get("summary") or "(No title)"),
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
        "calendar_color": calendar_color,
    }
    if "dateTime" in start_obj:
        return {
            **base,
            "start": str(start_obj["dateTime"]),
            "end": str(end_obj.get("dateTime")) if end_obj.get("dateTime") else None,
            "all_day": False,
        }
    if "date" in start_obj:
        return {
            **base,
            "start": str(start_obj["date"]),
            "end": str(end_obj.get("date")) if end_obj.get("date") else None,
            "all_day": True,
        }
    return None


def _list_calendar_events(
    client: httpx.Client,
    access_token: str,
    calendar: dict[str, Any],
    *,
    time_min: str,
    time_max: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        params: dict[str, str] = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": "250",
        }
        if page_token:
            params["pageToken"] = page_token
        resp = client.get(
            _events_url(str(calendar["id"])),
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        if resp.status_code >= 400:
            # Skip calendars the token can't read rather than failing the week.
            break
        data = resp.json()
        for item in data.get("items") or []:
            parsed = _parse_event(
                item,
                calendar_id=str(calendar["id"]),
                calendar_name=str(calendar["summary"]),
                calendar_color=calendar.get("color"),
            )
            if parsed:
                events.append(parsed)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return events


def list_week_events(
    refresh_token: str,
    *,
    start: date | None = None,
) -> tuple[date, date, list[dict[str, Any]]]:
    week_start, week_end = week_bounds(start)
    access_token = refresh_access_token(refresh_token)

    time_min = datetime(
        week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc
    ).isoformat()
    time_max = datetime(
        week_end.year, week_end.month, week_end.day, tzinfo=timezone.utc
    ).isoformat()

    events: list[dict[str, Any]] = []
    with httpx.Client(timeout=45.0) as client:
        calendars = _list_calendars(client, access_token)
        for calendar in calendars:
            events.extend(
                _list_calendar_events(
                    client,
                    access_token,
                    calendar,
                    time_min=time_min,
                    time_max=time_max,
                )
            )

    events.sort(key=lambda e: (e.get("start") or "", e.get("title") or ""))
    return week_start, week_end, events
