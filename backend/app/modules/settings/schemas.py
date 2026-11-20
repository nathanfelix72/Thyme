from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["ollama", "openai", "anthropic"]


class SettingsPublic(BaseModel):
    user_id: str
    provider: Provider = "ollama"
    ollama_model: str = "qwen2.5:7b"
    has_openai_key: bool = False
    has_anthropic_key: bool = False
    openai_key_hint: str | None = None
    anthropic_key_hint: str | None = None


class SettingsUpdate(BaseModel):
    provider: Provider | None = None
    ollama_model: str | None = None
    openai_api_key: str | None = Field(
        default=None,
        description="Set to a new key, or empty string to clear.",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Set to a new key, or empty string to clear.",
    )


class TestChatRequest(BaseModel):
    message: str = "Say hello in one short sentence."


class TestChatResponse(BaseModel):
    provider: Provider
    reply: str
