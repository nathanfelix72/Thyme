"""Google Calendar OAuth + week endpoints (mocked Google HTTP)."""

from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest


@pytest.fixture()
def google_env(tmp_data, monkeypatch):
    from app.modules.shared import config

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        config,
        "GOOGLE_REDIRECT_URI",
        "http://127.0.0.1:8765/api/calendar/google/callback",
    )
    monkeypatch.setattr(config, "FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setattr(config, "THYME_SECRETS_KEY", "")
    return tmp_data


def test_google_status_not_connected(client, google_env):
    res = client.get("/api/calendar/google/status")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is True
    assert body["connected"] is False
    assert body["email"] is None
    assert "callback" in body["redirect_uri"]


def test_auth_url_requires_config(client, tmp_data, monkeypatch):
    from app.modules.shared import config

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "")
    res = client.get("/api/calendar/google/auth-url")
    assert res.status_code == 501


def test_save_app_credentials_enables_connect(client, tmp_data, monkeypatch):
    from app.modules.shared import config

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(config, "THYME_SECRETS_KEY", "")

    before = client.get("/api/calendar/google/status").json()
    assert before["configured"] is False

    res = client.put(
        "/api/calendar/google/app-credentials",
        json={
            "client_id": "ui-client.apps.googleusercontent.com",
            "client_secret": "ui-secret",
        },
    )
    assert res.status_code == 200
    assert res.json()["configured"] is True

    auth = client.get("/api/calendar/google/auth-url")
    assert auth.status_code == 200
    assert "ui-client.apps.googleusercontent.com" in auth.json()["url"]


def test_auth_url_contains_state(client, google_env):
    res = client.get("/api/calendar/google/auth-url")
    assert res.status_code == 200
    url = res.json()["url"]
    parsed = urlparse(url)
    assert parsed.netloc == "accounts.google.com"
    qs = parse_qs(parsed.query)
    assert qs["client_id"] == ["test-client-id"]
    assert "calendar.readonly" in qs["scope"][0]
    assert qs["access_type"] == ["offline"]
    assert qs["state"][0]


def test_callback_saves_refresh_token(client, google_env, monkeypatch):
    from app.modules.calendar import google_client
    from app.modules.calendar.oauth_state import encode_oauth_state
    from app.modules.settings.store import get_store

    state = encode_oauth_state("local-dev")

    def fake_exchange(code: str):
        assert code == "auth-code"
        return {
            "refresh_token": "refresh-xyz",
            "access_token": "access-xyz",
        }

    monkeypatch.setattr(google_client, "exchange_code", fake_exchange)
    monkeypatch.setattr(
        google_client, "fetch_user_email", lambda _tok: "me@example.com"
    )

    res = client.get(
        "/api/calendar/google/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert "/plan?google=connected" in res.headers["location"]

    settings = get_store().get("local-dev")
    assert settings.google_refresh_token == "refresh-xyz"
    assert settings.google_calendar_email == "me@example.com"

    status = client.get("/api/calendar/google/status").json()
    assert status["connected"] is True
    assert status["email"] == "me@example.com"


def test_week_returns_events(client, google_env, monkeypatch):
    from app.modules.calendar import google_client
    from app.modules.settings.store import get_store

    store = get_store()
    settings = store.get("local-dev")
    settings.google_refresh_token = "refresh-xyz"
    settings.google_calendar_email = "me@example.com"
    store.save(settings)

    week_start = date(2026, 11, 23)  # Monday

    def fake_list(refresh_token: str, *, start=None):
        assert refresh_token == "refresh-xyz"
        return (
            week_start,
            date(2026, 11, 30),
            [
                {
                    "id": "primary:evt1",
                    "title": "Standup",
                    "start": "2026-11-23T15:00:00-07:00",
                    "end": "2026-11-23T15:30:00-07:00",
                    "all_day": False,
                    "calendar_id": "primary",
                    "calendar_name": "Primary",
                    "calendar_color": "#3f6b45",
                },
                {
                    "id": "work:evt2",
                    "title": "Holiday",
                    "start": "2026-11-26",
                    "end": "2026-11-27",
                    "all_day": True,
                    "calendar_id": "work",
                    "calendar_name": "Work",
                    "calendar_color": "#4285f4",
                },
            ],
        )

    monkeypatch.setattr(google_client, "list_week_events", fake_list)

    res = client.get("/api/calendar/week", params={"start": "2026-11-23"})
    assert res.status_code == 200
    body = res.json()
    assert body["connected"] is True
    assert body["start"] == "2026-11-23"
    assert len(body["events"]) == 2
    assert body["events"][0]["title"] == "Standup"
    assert body["events"][1]["all_day"] is True


def test_disconnect_clears_token(client, google_env):
    from app.modules.settings.store import get_store

    store = get_store()
    settings = store.get("local-dev")
    settings.google_refresh_token = "refresh-xyz"
    settings.google_calendar_email = "me@example.com"
    store.save(settings)

    res = client.delete("/api/calendar/google")
    assert res.status_code == 200
    body = res.json()
    assert body["connected"] is False

    settings = get_store().get("local-dev")
    assert settings.google_refresh_token is None
    assert settings.google_calendar_email is None


def test_week_bounds_sunday():
    from app.modules.calendar.google_client import week_bounds

    start, end = week_bounds(date(2026, 11, 26))  # Thursday → snap to Sun 22
    assert start == date(2026, 11, 22)
    assert end == date(2026, 11, 29)

    s2, e2 = week_bounds()
    assert (e2 - s2).days == 7
    assert s2.weekday() == 6  # Sunday
