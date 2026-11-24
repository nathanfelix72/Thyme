"""Per-task LLM provider overrides."""

from __future__ import annotations

from app.modules.settings.schemas import TaskProviders
from app.modules.settings.store import UserSettings, _normalize_task_providers


def test_provider_for_falls_back_to_default():
    settings = UserSettings(user_id="u1", provider="ollama")
    assert settings.provider_for("summarize") == "ollama"
    assert settings.provider_for(None) == "ollama"


def test_provider_for_uses_task_override():
    settings = UserSettings(
        user_id="u1",
        provider="ollama",
        task_providers={
            "summarize": "ollama",
            "suggest_side": "anthropic",
            "web_clean": "openai",
        },
    )
    assert settings.provider_for("summarize") == "ollama"
    assert settings.provider_for("suggest_side") == "anthropic"
    assert settings.provider_for("web_clean") == "openai"
    assert settings.provider_for("scale") == "ollama"


def test_normalize_task_providers_drops_invalid():
    cleaned = _normalize_task_providers(
        {
            "summarize": "anthropic",
            "suggest_side": "nope",
            "extra": "openai",
            "scale": None,
        }
    )
    assert cleaned == {"summarize": "anthropic"}


def test_public_dict_includes_all_tasks():
    settings = UserSettings(
        user_id="u1",
        provider="openai",
        task_providers={"web_clean": "anthropic"},
    )
    public = settings.public_dict()
    tasks = public["task_providers"]
    assert tasks["web_clean"] == "anthropic"
    assert tasks["summarize"] is None
    assert tasks["suggest_side"] is None
    assert tasks["scale"] is None
    assert tasks["segment"] is None


def test_settings_roundtrip_task_providers(client):
    res = client.put(
        "/api/settings",
        json={
            "provider": "ollama",
            "task_providers": {
                "summarize": "ollama",
                "suggest_side": "anthropic",
                "web_clean": None,
                "scale": "openai",
                "segment": None,
            },
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "ollama"
    assert body["task_providers"]["suggest_side"] == "anthropic"
    assert body["task_providers"]["scale"] == "openai"
    assert body["task_providers"]["web_clean"] is None

    got = client.get("/api/settings")
    assert got.status_code == 200
    assert got.json()["task_providers"]["suggest_side"] == "anthropic"

    parsed = TaskProviders.model_validate(got.json()["task_providers"])
    assert parsed.suggest_side == "anthropic"
    assert parsed.web_clean is None


def test_profile_fields_roundtrip(client):
    res = client.put(
        "/api/settings",
        json={
            "display_name": "Nate",
            "theme": "dark",
            "units": "metric",
            "default_servings": 6,
            "always_exclude_ingredients": ["peanuts", "shellfish"],
            "inactive_calendar_ids": ["cal-work", "cal-family"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["display_name"] == "Nate"
    assert body["theme"] == "dark"
    assert body["units"] == "metric"
    assert body["default_servings"] == 6
    assert body["always_exclude_ingredients"] == ["peanuts", "shellfish"]
    assert body["inactive_calendar_ids"] == ["cal-work", "cal-family"]

    got = client.get("/api/settings").json()
    assert got["display_name"] == "Nate"
    assert got["theme"] == "dark"
    assert got["inactive_calendar_ids"] == ["cal-work", "cal-family"]


def test_user_model_uses_task_override(monkeypatch):
    from app.modules.recipes import normalize
    from app.modules.settings.store import UserSettings

    captured: dict[str, str] = {}

    def fake_build(provider, **kwargs):
        captured["provider"] = provider
        return object()

    monkeypatch.setattr(
        normalize,
        "get_store",
        lambda: type(
            "S",
            (),
            {
                "get": staticmethod(
                    lambda _uid: UserSettings(
                        user_id="u1",
                        provider="ollama",
                        task_providers={"suggest_side": "anthropic"},
                        anthropic_api_key="sk-ant-test",
                    )
                )
            },
        )(),
    )
    monkeypatch.setattr(normalize, "build_chat_model", fake_build)

    normalize._user_model("u1", task="suggest_side")
    assert captured["provider"] == "anthropic"

    normalize._user_model("u1", task="summarize")
    assert captured["provider"] == "ollama"
