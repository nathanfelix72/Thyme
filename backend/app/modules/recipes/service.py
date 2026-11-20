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
    """Placeholder shape for a stored recipe."""

    id: str
    title: str
    body: str


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
