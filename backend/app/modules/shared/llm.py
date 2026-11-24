"""Chat model factory — Ollama by default, frontier models via BYOK."""

from __future__ import annotations

import os
from typing import Any, Literal

from langchain.chat_models import init_chat_model

from app.modules.shared import config

Provider = Literal["ollama", "openai", "anthropic"]


def build_chat_model(
    provider: Provider,
    *,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_model: str | None = None,
    temperature: float | None = None,
) -> Any:
    """Return a LangChain chat model for the chosen provider.

    - ollama: local qwen2.5:7b (labs default) — no user key
    - openai / anthropic: uses the caller's BYOK key only
    - temperature: optional override (use 0 for deterministic extraction)
    """
    extra: dict[str, Any] = {}
    if temperature is not None:
        extra["temperature"] = temperature

    if provider == "ollama":
        model = ollama_model or config.OLLAMA_MODEL
        # init_chat_model reads OLLAMA_HOST from env when present
        os.environ.setdefault("OLLAMA_HOST", config.OLLAMA_HOST)
        return init_chat_model(f"ollama:{model}", **extra)

    if provider == "openai":
        if not openai_api_key:
            raise ValueError("OpenAI provider selected but no API key is saved.")
        return init_chat_model("openai:gpt-4o-mini", api_key=openai_api_key, **extra)

    if provider == "anthropic":
        if not anthropic_api_key:
            raise ValueError("Anthropic provider selected but no API key is saved.")
        return init_chat_model(
            "anthropic:claude-haiku-4-5",
            api_key=anthropic_api_key,
            **extra,
        )

    raise ValueError(f"Unknown provider: {provider}")
