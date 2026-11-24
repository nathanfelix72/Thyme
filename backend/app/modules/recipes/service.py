"""Recipe persistence.

Local: one JSON file under backend/data/ (gitignored), keyed by user.
Later: swap LocalRecipeStore for a DynamoDB / Postgres store with the same
RecipeStore interface -- routes don't need to change.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from app.modules.recipes.schemas import Recipe
from app.modules.shared import config


class StoredRecipe(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    source_filename: str | None = None
    source_url: str | None = None
    recipe: Recipe


class RecipeStore(Protocol):
    def create(
        self,
        user_id: str,
        recipe: Recipe,
        source_filename: str | None = None,
        source_url: str | None = None,
    ) -> StoredRecipe: ...

    def get(self, user_id: str, recipe_id: str) -> StoredRecipe | None: ...

    def list_all(self, user_id: str) -> list[StoredRecipe]: ...

    def delete(self, user_id: str, recipe_id: str) -> bool: ...


class LocalRecipeStore:
    """Dev/laptop store: {user_id: {recipe_id: StoredRecipe-json}} in one file."""

    _lock = threading.Lock()  # FastAPI runs sync routes in a threadpool

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.DATA_DIR / "recipes.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _read_all(self) -> dict[str, dict[str, dict]]:
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _write_all(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.path)  # atomic swap so a crash can't leave half a file

    def create(
        self,
        user_id: str,
        recipe: Recipe,
        source_filename: str | None = None,
        source_url: str | None = None,
    ) -> StoredRecipe:
        stored = StoredRecipe(
            id=uuid.uuid4().hex,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            source_filename=source_filename,
            source_url=source_url,
            recipe=recipe,
        )
        with self._lock:
            data = self._read_all()
            data.setdefault(user_id, {})[stored.id] = stored.model_dump(mode="json")
            self._write_all(data)
        return stored

    def get(self, user_id: str, recipe_id: str) -> StoredRecipe | None:
        with self._lock:
            raw = self._read_all().get(user_id, {}).get(recipe_id)
        return StoredRecipe.model_validate(raw) if raw else None

    def list_all(self, user_id: str) -> list[StoredRecipe]:
        with self._lock:
            rows = self._read_all().get(user_id, {}).values()
        recipes = [StoredRecipe.model_validate(r) for r in rows]
        return sorted(recipes, key=lambda r: r.created_at, reverse=True)

    def delete(self, user_id: str, recipe_id: str) -> bool:
        with self._lock:
            data = self._read_all()
            if recipe_id not in data.get(user_id, {}):
                return False
            del data[user_id][recipe_id]
            self._write_all(data)
        return True


def get_recipe_store() -> RecipeStore:
    # TODO: return a DynamoDB/Postgres store when config.THYME_ENV == "aws"
    return LocalRecipeStore()
