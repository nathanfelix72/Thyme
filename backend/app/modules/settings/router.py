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

    if body.openai_api_key is not None:
        current.openai_api_key = body.openai_api_key.strip() or None
    if body.anthropic_api_key is not None:
        current.anthropic_api_key = body.anthropic_api_key.strip() or None

    saved = store.save(current)
    return SettingsPublic(**saved.public_dict())


@router.post("/test-chat", response_model=TestChatResponse)
def test_chat(
    body: TestChatRequest,
    user_id: str = Depends(get_current_user_id),
) -> TestChatResponse:
    """Smoke-test the selected provider (Ollama local or BYOK frontier)."""
    settings = get_store().get(user_id)
    try:
        model = build_chat_model(
            settings.provider,
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            ollama_model=settings.ollama_model,
        )
        result = model.invoke(body.message)
        reply = getattr(result, "content", None) or str(result)
    except Exception as exc:  # noqa: BLE001 — surface provider errors to the UI
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TestChatResponse(provider=settings.provider, reply=str(reply))
