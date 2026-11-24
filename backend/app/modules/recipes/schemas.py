"""Structured recipe schema produced by Intelligent Document Analysis.

Adapted from lab3 IDA's ClimateDisclosure model: field descriptions double as
guidance in the JSON schema sent to the model, and a validator strips any
item that's just a description parroted back as "extracted" content.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

Difficulty = Literal["easy", "medium", "hard"]


def _normalize(text: str) -> str:
    """Lowercase and collapse non-alphanumerics so punctuation/case don't
    defeat an exact-match comparison."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class Ingredient(BaseModel):
    name: str = Field(description="Ingredient name without quantity, e.g. 'yellow onion'")
    quantity: float | None = Field(
        default=None,
        description="Numeric amount (convert fractions: 1 1/2 -> 1.5). Null if unspecified, e.g. 'salt to taste'",
    )
    unit: str | None = Field(
        default=None,
        description="Unit of measure such as cup, tbsp, g, oz. Null for countable items like '2 eggs'",
    )
    notes: str | None = Field(
        default=None,
        description="Preparation notes such as 'diced' or 'room temperature'",
    )


class Recipe(BaseModel):
    title: str = Field(description="The recipe's name")
    servings: int | None = Field(default=None, description="Number of servings the recipe makes")
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(
        default_factory=list,
        description="Ordered cooking instructions, one step per item",
    )
    difficulty: Difficulty = Field(description="Overall difficulty: easy, medium, or hard")
    prep_time_minutes: int | None = Field(default=None, description="Active preparation time in minutes")
    cook_time_minutes: int | None = Field(default=None, description="Cooking or baking time in minutes")
    total_time_minutes: int | None = Field(
        default=None,
        description="Total time in minutes including passive time such as marinating or resting",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Short lowercase tags for cuisine, meal type, diet, and main ingredient",
    )

    @field_validator("steps", "tags", mode="after")
    @classmethod
    def drop_parroted_description(cls, items: list[str], info: ValidationInfo) -> list[str]:
        """Drop list items that are just this field's description echoed back
        (qwen2.5:7b did this in lab3 when unsure). Cleanup, not a retry trigger:
        at temperature 0 a retry would just parrot it again."""
        target = _normalize(cls.model_fields[info.field_name].description or "")
        return [item for item in items if item.strip() and _normalize(item) != target]

    @field_validator("tags", mode="after")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        seen: list[str] = []
        for tag in tags:
            t = tag.strip().lower()
            if t and t not in seen:
                seen.append(t)
        return seen


class ExtractionResult(BaseModel):
    """API response for /api/recipes/upload."""

    id: str
    recipe: Recipe
    source: Literal["file", "text", "url_jsonld", "url_page_text"]
    attempts: int
    source_chars: int
