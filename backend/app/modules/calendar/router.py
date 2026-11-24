"""Calendar / meal-plan API — Google Calendar connect + week events."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.modules.calendar import google_client
from app.modules.calendar.app_credentials import (
    clear_stored_credentials,
    save_stored_credentials,
)
from app.modules.calendar.oauth_state import decode_oauth_state, encode_oauth_state
from app.modules.calendar.schemas import (
    CalendarEvent,
    GoogleAppCredentialsUpdate,
    GoogleAuthUrl,
    GoogleStatus,
    WeekPlan,
)
from app.modules.shared import config
from app.modules.shared.auth import get_current_user_id
from app.modules.settings.store import get_store

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _require_google_configured() -> None:
    if not google_client.google_configured():
        raise HTTPException(
            status_code=501,
            detail=(
                "Google Calendar isn’t set up for this app yet. "
                "Use the setup form on the Plan page (one-time)."
            ),
        )


def _status_for(user_id: str) -> GoogleStatus:
    settings = get_store().get(user_id)
    return GoogleStatus(
        configured=google_client.google_configured(),
        connected=bool(settings.google_refresh_token),
        email=settings.google_calendar_email,
        redirect_uri=google_client.redirect_uri(),
        can_configure=True,
    )


@router.get("/google/status", response_model=GoogleStatus)
def google_status(user_id: str = Depends(get_current_user_id)) -> GoogleStatus:
    return _status_for(user_id)


@router.put("/google/app-credentials", response_model=GoogleStatus)
def save_google_app_credentials(
    body: GoogleAppCredentialsUpdate,
    user_id: str = Depends(get_current_user_id),
) -> GoogleStatus:
    """One-time app setup: store Google OAuth Web client id/secret."""
    try:
        save_stored_credentials(body.client_id, body.client_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _status_for(user_id)


@router.delete("/google/app-credentials", response_model=GoogleStatus)
def delete_google_app_credentials(
    user_id: str = Depends(get_current_user_id),
) -> GoogleStatus:
    """Remove UI-saved app credentials (env vars still apply if set)."""
    clear_stored_credentials()
    return _status_for(user_id)


@router.get("/google/auth-url", response_model=GoogleAuthUrl)
def google_auth_url(user_id: str = Depends(get_current_user_id)) -> GoogleAuthUrl:
    _require_google_configured()
    state = encode_oauth_state(user_id)
    return GoogleAuthUrl(url=google_client.build_auth_url(state))


@router.get("/google/callback")
def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Browser redirect from Google — no Cognito header; user_id is in state."""
    frontend = f"{config.FRONTEND_ORIGIN}/plan"

    if error:
        qs = urlencode({"google": "error", "detail": error})
        return RedirectResponse(url=f"{frontend}?{qs}", status_code=302)

    if not code or not state:
        qs = urlencode({"google": "error", "detail": "missing_code_or_state"})
        return RedirectResponse(url=f"{frontend}?{qs}", status_code=302)

    try:
        user_id = decode_oauth_state(state)
    except ValueError:
        qs = urlencode({"google": "error", "detail": "invalid_state"})
        return RedirectResponse(url=f"{frontend}?{qs}", status_code=302)

    if not google_client.google_configured():
        qs = urlencode({"google": "error", "detail": "not_configured"})
        return RedirectResponse(url=f"{frontend}?{qs}", status_code=302)

    try:
        tokens = google_client.exchange_code(code)
    except Exception:  # noqa: BLE001 — surface as redirect, not JSON 500
        qs = urlencode({"google": "error", "detail": "token_exchange_failed"})
        return RedirectResponse(url=f"{frontend}?{qs}", status_code=302)

    refresh = tokens.get("refresh_token")
    access = tokens.get("access_token")
    if not refresh:
        store = get_store()
        existing = store.get(user_id)
        refresh = existing.google_refresh_token
    if not refresh:
        qs = urlencode({"google": "error", "detail": "no_refresh_token"})
        return RedirectResponse(url=f"{frontend}?{qs}", status_code=302)

    email: str | None = None
    if access:
        try:
            email = google_client.fetch_user_email(str(access))
        except Exception:  # noqa: BLE001
            email = None

    store = get_store()
    settings = store.get(user_id)
    settings.google_refresh_token = str(refresh)
    if email:
        settings.google_calendar_email = email
    store.save(settings)

    qs = urlencode({"google": "connected"})
    return RedirectResponse(url=f"{frontend}?{qs}", status_code=302)


@router.delete("/google", response_model=GoogleStatus)
def google_disconnect(user_id: str = Depends(get_current_user_id)) -> GoogleStatus:
    store = get_store()
    settings = store.get(user_id)
    settings.google_refresh_token = None
    settings.google_calendar_email = None
    store.save(settings)
    return _status_for(user_id)


@router.get("/week", response_model=WeekPlan)
def week_plan(
    start: str | None = Query(
        default=None,
        description="Week start date YYYY-MM-DD (defaults to Sunday of current week).",
    ),
    user_id: str = Depends(get_current_user_id),
) -> WeekPlan:
    settings = get_store().get(user_id)
    if not settings.google_refresh_token:
        week_start, week_end = google_client.week_bounds(_parse_start(start))
        return WeekPlan(
            connected=False,
            start=week_start.isoformat(),
            end=week_end.isoformat(),
            email=None,
            events=[],
        )

    _require_google_configured()

    try:
        week_start, week_end, raw_events = google_client.list_week_events(
            settings.google_refresh_token,
            start=_parse_start(start),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WeekPlan(
        connected=True,
        start=week_start.isoformat(),
        end=week_end.isoformat(),
        email=settings.google_calendar_email,
        events=[CalendarEvent(**ev) for ev in raw_events],
    )


def _parse_start(start: str | None) -> date | None:
    if not start:
        return None
    try:
        return date.fromisoformat(start)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="start must be YYYY-MM-DD"
        ) from exc
