from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["ollama", "openai", "anthropic"]
Theme = Literal["light", "dark", "system"]
Units = Literal["us", "metric"]

LlmTask = Literal[
    "web_clean",
    "summarize",
    "suggest_side",
    "scale",
    "segment",
]

LLM_TASKS: tuple[LlmTask, ...] = (
    "web_clean",
    "summarize",
    "suggest_side",
    "scale",
    "segment",
)


class TaskProviders(BaseModel):
    """Per-task provider overrides. Null / omitted = use the default provider."""

    web_clean: Provider | None = None
    summarize: Provider | None = None
    suggest_side: Provider | None = None
    scale: Provider | None = None
    segment: Provider | None = None


class SettingsPublic(BaseModel):
    user_id: str
    provider: Provider = "ollama"
    ollama_model: str = "qwen2.5:7b"
    task_providers: TaskProviders = Field(default_factory=TaskProviders)
    has_openai_key: bool = False
    has_anthropic_key: bool = False
    has_tavily_key: bool = False
    openai_key_hint: str | None = None
    anthropic_key_hint: str | None = None
    tavily_key_hint: str | None = None
    always_exclude_ingredients: list[str] = Field(default_factory=list)
    display_name: str | None = None
    theme: Theme = "system"
    units: Units = "us"
    default_servings: int = 4
    inactive_calendar_ids: list[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    provider: Provider | None = None
    ollama_model: str | None = None
    task_providers: TaskProviders | None = None
    openai_api_key: str | None = Field(
        default=None,
        description="Set to a new key, or empty string to clear.",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Set to a new key, or empty string to clear.",
    )
    tavily_api_key: str | None = Field(
        default=None,
        description="Set to a new key, or empty string to clear. Used for web recipe search.",
    )
    always_exclude_ingredients: list[str] | None = Field(
        default=None,
        description="Permanent allergy/exclude list applied on every search.",
    )
    display_name: str | None = Field(
        default=None,
        description="Set to a name, or empty string to clear.",
    )
    theme: Theme | None = None
    units: Units | None = None
    default_servings: int | None = Field(default=None, ge=1, le=48)
    inactive_calendar_ids: list[str] | None = Field(
        default=None,
        description="Google calendar ids marked inactive/hidden on Plan.",
    )


class TestChatRequest(BaseModel):
    message: str = "Say hello in one short sentence."
    provider: Provider | None = Field(
        default=None,
        description="Optional override; defaults to the saved default provider.",
    )


class TestChatResponse(BaseModel):
    provider: Provider
    reply: str
