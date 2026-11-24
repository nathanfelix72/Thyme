"""RAG search request/response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.recipes.schemas import Difficulty, Recipe


class SearchRequest(BaseModel):
    include_ingredients: list[str] = Field(default_factory=list)
    exclude_ingredients: list[str] = Field(default_factory=list)
    max_time_minutes: int | None = None
    difficulty: Difficulty | None = None
    cuisine: str | None = None
    tags: list[str] = Field(default_factory=list)
    query: str | None = None
    include_library: bool = True
    include_web: bool = False  # web is opt-in; Find never enables this
    limit: int = 8

    @model_validator(mode="after")
    def require_a_source(self) -> SearchRequest:
        if not self.include_library and not self.include_web:
            raise ValueError("Turn on Use your library and/or Search the web.")
        return self


class SearchHit(BaseModel):
    recipe: Recipe
    score: float
    reason: str
    origin: Literal["local", "web"] = "local"


class SearchResponse(BaseModel):
    results: list[SearchHit]
    web_queried: bool = False
    web_query: str | None = None
    web_imported: int = 0  # always 0 — web hits are previews until explicitly saved
    web_previews: int = 0
    activity: list[dict] = Field(default_factory=list)


class IndexRequest(BaseModel):
    recipe_id: str


class IndexResponse(BaseModel):
    indexed: bool
    recipe_id: str
