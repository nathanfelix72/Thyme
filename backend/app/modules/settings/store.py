"""Per-user settings + BYOK secret storage.

Local: encrypted JSON under backend/data/ (gitignored).
AWS Plan B: swap LocalSecretsStore for DynamoSecretsStore (same interface).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

from app.modules.shared import config
from app.modules.settings.schemas import LLM_TASKS, LlmTask, Provider, Theme, Units


def _mask(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "••••"
    return f"{key[:3]}…{key[-4:]}"


def _normalize_task_providers(raw: object) -> dict[str, Provider]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Provider] = {}
    for task in LLM_TASKS:
        val = raw.get(task)
        if val in ("ollama", "openai", "anthropic"):
            out[task] = val
    return out


def _normalize_theme(raw: object) -> Theme:
    if raw in ("light", "dark", "system"):
        return raw
    return "system"


def _normalize_units(raw: object) -> Units:
    if raw in ("us", "metric"):
        return raw
    return "us"


def _normalize_servings(raw: object) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 4
    return max(1, min(48, value))


@dataclass
class UserSettings:
    user_id: str
    provider: Provider = "ollama"
    ollama_model: str = "qwen2.5:7b"
    task_providers: dict[str, Provider] | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    always_exclude_ingredients: list[str] | None = None
    display_name: str | None = None
    theme: Theme = "system"
    units: Units = "us"
    default_servings: int = 4
    inactive_calendar_ids: list[str] | None = None
    google_refresh_token: str | None = None
    google_calendar_email: str | None = None

    def provider_for(self, task: LlmTask | None = None) -> Provider:
        """Resolve the provider for a task, falling back to the default."""
        if task and self.task_providers:
            override = self.task_providers.get(task)
            if override in ("ollama", "openai", "anthropic"):
                return override
        return self.provider

    def public_dict(self) -> dict:
        overrides = self.task_providers or {}
        return {
            "user_id": self.user_id,
            "provider": self.provider,
            "ollama_model": self.ollama_model,
            "task_providers": {task: overrides.get(task) for task in LLM_TASKS},
            "has_openai_key": bool(self.openai_api_key),
            "has_anthropic_key": bool(self.anthropic_api_key),
            "openai_key_hint": _mask(self.openai_api_key),
            "anthropic_key_hint": _mask(self.anthropic_api_key),
            "always_exclude_ingredients": list(
                self.always_exclude_ingredients or []
            ),
            "display_name": self.display_name,
            "theme": self.theme,
            "units": self.units,
            "default_servings": self.default_servings,
            "inactive_calendar_ids": list(self.inactive_calendar_ids or []),
        }

    @staticmethod
    def from_payload(user_id: str, payload: dict) -> UserSettings:
        return UserSettings(
            user_id=user_id,
            provider=payload.get("provider", "ollama"),
            ollama_model=payload.get("ollama_model", config.OLLAMA_MODEL),
            task_providers=_normalize_task_providers(payload.get("task_providers")),
            openai_api_key=payload.get("openai_api_key"),
            anthropic_api_key=payload.get("anthropic_api_key"),
            always_exclude_ingredients=list(
                payload.get("always_exclude_ingredients") or []
            ),
            display_name=(
                str(payload["display_name"]).strip() or None
                if payload.get("display_name") is not None
                else None
            ),
            theme=_normalize_theme(payload.get("theme")),
            units=_normalize_units(payload.get("units")),
            default_servings=_normalize_servings(payload.get("default_servings", 4)),
            inactive_calendar_ids=[
                str(item).strip()
                for item in (payload.get("inactive_calendar_ids") or [])
                if item and str(item).strip()
            ],
            google_refresh_token=payload.get("google_refresh_token"),
            google_calendar_email=payload.get("google_calendar_email"),
        )

    def secret_payload(self) -> dict:
        return {
            "provider": self.provider,
            "ollama_model": self.ollama_model,
            "task_providers": _normalize_task_providers(self.task_providers),
            "openai_api_key": self.openai_api_key,
            "anthropic_api_key": self.anthropic_api_key,
            "always_exclude_ingredients": list(
                self.always_exclude_ingredients or []
            ),
            "display_name": self.display_name,
            "theme": self.theme,
            "units": self.units,
            "default_servings": self.default_servings,
            "inactive_calendar_ids": list(self.inactive_calendar_ids or []),
            "google_refresh_token": self.google_refresh_token,
            "google_calendar_email": self.google_calendar_email,
        }


class SecretsStore(Protocol):
    def get(self, user_id: str) -> UserSettings: ...

    def save(self, settings: UserSettings) -> UserSettings: ...


def _fernet() -> Fernet:
    raw = config.THYME_SECRETS_KEY.strip()
    if raw:
        return Fernet(raw.encode())
    key_path = config.DATA_DIR / ".fernet_key"
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return Fernet(key_path.read_text(encoding="utf-8").strip().encode())
    generated = Fernet.generate_key()
    key_path.write_text(generated.decode(), encoding="utf-8")
    return Fernet(generated)


class LocalSecretsStore:
    """Dev/laptop store — one JSON file of encrypted per-user blobs."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.DATA_DIR / "user_secrets.json")
        self._fernet = _fernet()
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _read_all(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _write_all(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get(self, user_id: str) -> UserSettings:
        data = self._read_all()
        blob = data.get(user_id)
        if not blob:
            return UserSettings(user_id=user_id)
        try:
            raw = self._fernet.decrypt(blob.encode()).decode()
            payload = json.loads(raw)
        except (InvalidToken, json.JSONDecodeError):
            return UserSettings(user_id=user_id)
        return UserSettings.from_payload(user_id, payload)

    def save(self, settings: UserSettings) -> UserSettings:
        data = self._read_all()
        payload = settings.secret_payload()
        token = self._fernet.encrypt(json.dumps(payload).encode()).decode()
        data[settings.user_id] = token
        self._write_all(data)
        return settings


class DynamoSecretsStore:
    """Plan B — DynamoDB-backed store. Not wired until AWS deploy is approved."""

    def __init__(self, table_name: str | None = None, region: str | None = None) -> None:
        self.table_name = table_name or config.USER_SECRETS_TABLE
        self.region = region or config.AWS_REGION
        # Import deferred so local laptop testing does not require boto3 usage
        import boto3

        self._table = boto3.resource("dynamodb", region_name=self.region).Table(
            self.table_name
        )
        self._fernet = _fernet()

    def get(self, user_id: str) -> UserSettings:
        resp = self._table.get_item(Key={"user_id": user_id})
        item = resp.get("Item")
        if not item:
            return UserSettings(user_id=user_id)
        raw = self._fernet.decrypt(item["payload"].encode()).decode()
        payload = json.loads(raw)
        return UserSettings.from_payload(user_id, payload)

    def save(self, settings: UserSettings) -> UserSettings:
        payload = settings.secret_payload()
        token = self._fernet.encrypt(json.dumps(payload).encode()).decode()
        self._table.put_item(
            Item={
                "user_id": settings.user_id,
                "payload": token,
                "provider": settings.provider,
            }
        )
        return settings


def get_store() -> SecretsStore:
    if config.THYME_ENV == "aws":
        return DynamoSecretsStore()
    return LocalSecretsStore()
