"""Per-user recipe persistence.

Local: JSON under backend/data/recipes/.
AWS: DynamoDB thyme-recipes (user_id PK, recipe_id SK).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from app.modules.recipes.schemas import Recipe
from app.modules.shared import config


class RecipeStore(Protocol):
    def put(self, recipe: Recipe) -> Recipe: ...

    def get(self, user_id: str, recipe_id: str) -> Recipe | None: ...

    def list_for_user(self, user_id: str) -> list[Recipe]: ...

    def put_many(self, recipes: list[Recipe]) -> list[Recipe]: ...

    def delete(self, user_id: str, recipe_id: str) -> bool: ...


class LocalRecipeStore:
    """Laptop store — one JSON file per user."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (config.DATA_DIR / "recipes")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return self.root / f"{safe}.json"

    def _read(self, user_id: str) -> dict[str, Any]:
        path = self._path(user_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8") or "{}")

    def _write(self, user_id: str, data: dict[str, Any]) -> None:
        self._path(user_id).write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    def put(self, recipe: Recipe) -> Recipe:
        data = self._read(recipe.user_id)
        data[recipe.recipe_id] = recipe.model_dump()
        self._write(recipe.user_id, data)
        return recipe

    def put_many(self, recipes: list[Recipe]) -> list[Recipe]:
        if not recipes:
            return []
        user_id = recipes[0].user_id
        data = self._read(user_id)
        for recipe in recipes:
            data[recipe.recipe_id] = recipe.model_dump()
        self._write(user_id, data)
        return recipes

    def get(self, user_id: str, recipe_id: str) -> Recipe | None:
        raw = self._read(user_id).get(recipe_id)
        return Recipe.model_validate(raw) if raw else None

    def list_for_user(self, user_id: str) -> list[Recipe]:
        return [
            Recipe.model_validate(raw)
            for raw in self._read(user_id).values()
        ]

    def delete(self, user_id: str, recipe_id: str) -> bool:
        data = self._read(user_id)
        if recipe_id not in data:
            return False
        del data[recipe_id]
        self._write(user_id, data)
        return True


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


class DynamoRecipeStore:
    """AWS store — DynamoDB table thyme-recipes."""

    def __init__(self, table_name: str | None = None, region: str | None = None) -> None:
        import boto3

        self.table_name = table_name or config.RECIPES_TABLE
        self.region = region or config.AWS_REGION
        self._table = boto3.resource("dynamodb", region_name=self.region).Table(
            self.table_name
        )

    def put(self, recipe: Recipe) -> Recipe:
        item = _to_dynamo(recipe.model_dump())
        self._table.put_item(Item=item)
        return recipe

    def put_many(self, recipes: list[Recipe]) -> list[Recipe]:
        for recipe in recipes:
            self.put(recipe)
        return recipes

    def get(self, user_id: str, recipe_id: str) -> Recipe | None:
        resp = self._table.get_item(Key={"user_id": user_id, "recipe_id": recipe_id})
        item = resp.get("Item")
        if not item:
            return None
        return Recipe.model_validate(_from_dynamo(item))

    def list_for_user(self, user_id: str) -> list[Recipe]:
        resp = self._table.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
        )
        return [
            Recipe.model_validate(_from_dynamo(item))
            for item in resp.get("Items", [])
        ]

    def delete(self, user_id: str, recipe_id: str) -> bool:
        existing = self.get(user_id, recipe_id)
        if not existing:
            return False
        self._table.delete_item(Key={"user_id": user_id, "recipe_id": recipe_id})
        return True


def get_recipe_store() -> RecipeStore:
    if config.THYME_ENV == "aws":
        return DynamoRecipeStore()
    return LocalRecipeStore()
