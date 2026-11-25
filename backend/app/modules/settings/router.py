"""User settings + BYOK + provider test chat."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.shared.auth import get_current_user_id
from app.modules.shared.llm import build_chat_model
from app.modules.settings.schemas import (
    SettingsPublic,
    SettingsUpdate,
    TestChatRequest,
    TestChatResponse,
)
from app.modules.settings.store import get_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsPublic)
def get_settings(user_id: str = Depends(get_current_user_id)) -> SettingsPublic:
    settings = get_store().get(user_id)
    return SettingsPublic(**settings.public_dict())


@router.put("", response_model=SettingsPublic)
def update_settings(
    body: SettingsUpdate,
    user_id: str = Depends(get_current_user_id),
) -> SettingsPublic:
    store = get_store()
    current = store.get(user_id)

    if body.provider is not None:
        current.provider = body.provider
    if body.ollama_model is not None:
        current.ollama_model = body.ollama_model.strip() or current.ollama_model
    if body.task_providers is not None:
        current.task_providers = {
            task: provider
            for task, provider in body.task_providers.model_dump().items()
            if provider in ("ollama", "openai", "anthropic")
        }

    if body.openai_api_key is not None:
        current.openai_api_key = body.openai_api_key.strip() or None
    if body.anthropic_api_key is not None:
        current.anthropic_api_key = body.anthropic_api_key.strip() or None
    if body.tavily_api_key is not None:
        current.tavily_api_key = body.tavily_api_key.strip() or None
    if body.always_exclude_ingredients is not None:
        current.always_exclude_ingredients = [
            item.strip()
            for item in body.always_exclude_ingredients
            if item and item.strip()
        ]
    if body.display_name is not None:
        current.display_name = body.display_name.strip() or None
    if body.theme is not None:
        current.theme = body.theme
    if body.units is not None:
        current.units = body.units
    if body.default_servings is not None:
        current.default_servings = body.default_servings
    if body.inactive_calendar_ids is not None:
        current.inactive_calendar_ids = [
            item.strip()
            for item in body.inactive_calendar_ids
            if item and str(item).strip()
        ]

    saved = store.save(current)
    return SettingsPublic(**saved.public_dict())


@router.post("/test-chat", response_model=TestChatResponse)
def test_chat(
    body: TestChatRequest,
    user_id: str = Depends(get_current_user_id),
) -> TestChatResponse:
    """Smoke-test a provider (default, or an explicit override)."""
    settings = get_store().get(user_id)
    provider = body.provider or settings.provider
    try:
        model = build_chat_model(
            provider,
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            ollama_model=settings.ollama_model,
        )
        result = model.invoke(body.message)
        reply = getattr(result, "content", None) or str(result)
    except Exception as exc:  # noqa: BLE001 — surface provider errors to the UI
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TestChatResponse(provider=provider, reply=str(reply))
