"""Recipe storage service stubs.

Next sprint flow (do not implement yet):
1. Accept uploaded recipe files / structured recipe payloads
2. Persist recipes in a database
3. Hand off text to the RAG module for embedding + indexing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RecipeRecord:
    """Recipe shape shared by the seed catalog and future recipe storage."""

    id: str
    title: str
    body: str
    prep_minutes: int = 0
    ingredients: tuple[str, ...] = ()
    instructions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def search_text(self) -> str:
        return "\n".join(
            (
                self.title,
                self.body,
                f"Preparation time: {self.prep_minutes} minutes",
                f"Ingredients: {', '.join(self.ingredients)}",
                f"Tags: {', '.join(self.tags)}",
            )
        )


class RecipeStore(Protocol):
    """Interface for recipe persistence.

    TODO: implement with Postgres (and later pgvector handoff via rag).
    """

    def create(self, title: str, body: str) -> RecipeRecord: ...

    def get(self, recipe_id: str) -> RecipeRecord | None: ...

    def list_all(self) -> list[RecipeRecord]: ...


class InMemoryRecipeStoreStub:
    """Non-persistent stub so the team has a clear swap point."""

    def create(self, title: str, body: str) -> RecipeRecord:
        raise NotImplementedError("TODO: persist uploaded recipes")

    def get(self, recipe_id: str) -> RecipeRecord | None:
        raise NotImplementedError("TODO: fetch recipe by id")

    def list_all(self) -> list[RecipeRecord]:
        raise NotImplementedError("TODO: list recipes")
