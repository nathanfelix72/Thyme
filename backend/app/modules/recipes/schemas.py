"""Canonical recipe schemas — raw text is source of truth; metadata is filter columns."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]
RecipeSource = Literal["upload", "web"]


class Ingredient(BaseModel):
    """Legacy optional structured ingredient — not required for ingest."""

    name: str
    quantity: str | None = None
    unit: str | None = None


class Recipe(BaseModel):
    user_id: str
    recipe_id: str
    source: RecipeSource
    title: str
    raw_text: str = ""
    difficulty: Difficulty | None = None
    total_time_minutes: int | None = None
    servings: int | None = None
    cuisine: str | None = None
    tags: list[str] = Field(default_factory=list)
    ingredient_keywords: list[str] = Field(default_factory=list)
    # Optional / usually empty — kept for backward compatibility with stored items
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_doc: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def embed_text(self) -> str:
        """Text used for semantic indexing — title + raw body + keywords."""
        parts = [
            self.title,
            self.raw_text,
            " ".join(self.ingredient_keywords),
            " ".join(self.tags),
            self.cuisine or "",
            self.difficulty or "",
        ]
        return "\n".join(p for p in parts if p).strip() or self.title

    def filter_blob(self) -> str:
        """Lowercased text used for include/exclude matching."""
        return " ".join(
            [
                self.title,
                self.raw_text,
                " ".join(self.ingredient_keywords),
                " ".join(i.name for i in self.ingredients),
            ]
        ).lower()

    def summary(self) -> RecipeSummary:
        preview = (self.raw_text or "").strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:157] + "…"
        return RecipeSummary(
            recipe_id=self.recipe_id,
            title=self.title,
            source=self.source,
            difficulty=self.difficulty,
            total_time_minutes=self.total_time_minutes,
            cuisine=self.cuisine,
            ingredient_keywords=list(self.ingredient_keywords),
            preview=preview,
            source_doc=self.source_doc,
            source_url=self.source_url,
        )


class RecipeSummary(BaseModel):
    recipe_id: str
    title: str
    source: RecipeSource
    difficulty: Difficulty | None = None
    total_time_minutes: int | None = None
    cuisine: str | None = None
    ingredient_keywords: list[str] = Field(default_factory=list)
    preview: str = ""
    source_doc: str | None = None
    source_url: str | None = None


class RecipeSegment(BaseModel):
    """Verbatim segment sliced from source text — never LLM-rewritten."""

    title: str
    raw_text: str


class RecipeLocator(BaseModel):
    """Tiny LLM output: where a recipe starts in the source text."""

    title: str
    start_hint: str = ""


class RecipeLocatorBatch(BaseModel):
    recipes: list[RecipeLocator] = Field(default_factory=list)


class RecipeSegmentBatch(BaseModel):
    """Legacy shape — prefer RecipeLocatorBatch for new segment calls."""

    recipes: list[RecipeSegment] = Field(default_factory=list)


class WebRecipeClean(BaseModel):
    """Structured LLM output for noisy web recipe pages (Lab3-style)."""

    title: str = ""
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    difficulty: Difficulty = "medium"
    total_time_minutes: int = 30
    servings: int = 4
    cuisine: str = "general"
    ingredient_keywords: list[str] = Field(default_factory=list)


class RecipeMetadata(BaseModel):
    """Filter/cook columns derived from raw text — never rewrites body text."""

    difficulty: Difficulty | None = None
    total_time_minutes: int | None = None
    servings: int | None = None
    cuisine: str | None = None
    ingredient_keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    uploaded: int
    recipes: list[RecipeSummary]


class RecipeListResponse(BaseModel):
    recipes: list[RecipeSummary]


class RecipeUpdate(BaseModel):
    """Partial update for a library recipe. Omitted fields are left unchanged."""

    title: str | None = None
    raw_text: str | None = None
    difficulty: Difficulty | None = None
    total_time_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    servings: int | None = Field(default=None, ge=1, le=48)
    cuisine: str | None = None
    tags: list[str] | None = None
    ingredient_keywords: list[str] | None = None
    ingredients: list[Ingredient] | None = None
    steps: list[str] | None = None
    source_url: str | None = None


class RecipeAssistInput(BaseModel):
    """Recipe payload for single-shot helpers (works for library + web previews)."""

    title: str
    raw_text: str = ""
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    servings: int | None = None
    cuisine: str | None = None
    difficulty: Difficulty | None = None


class SummarizeOut(BaseModel):
    summary: str


class SummarizeResponse(BaseModel):
    summary: str


class SuggestSideOut(BaseModel):
    sides: list[str] = Field(default_factory=list)
    notes: str = ""


class SuggestSideResponse(BaseModel):
    sides: list[str]
    notes: str = ""


class ScaleServingsRequest(RecipeAssistInput):
    target_servings: int = Field(default=4, ge=1, le=48)


class ScaleServingsOut(BaseModel):
    ingredients: list[Ingredient] = Field(default_factory=list)
    notes: str = ""


class ScaleServingsResponse(BaseModel):
    target_servings: int
    ingredients: list[Ingredient]
    notes: str = ""
