"""Phase 1 semantic recipe retrieval and grounded chat."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import OllamaEmbeddings

from app.modules.recipes.catalog import SEED_RECIPES
from app.modules.recipes.service import RecipeRecord
from app.modules.shared import config
from app.modules.shared.llm import build_chat_model
from app.modules.settings.store import UserSettings


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class RecipeMatch:
    recipe: RecipeRecord
    score: float


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    recipes: list[RecipeMatch]


@lru_cache(maxsize=4)
def _get_embedder(model: str, host: str) -> Embedder:
    return OllamaEmbeddings(model=model, base_url=host)


@lru_cache(maxsize=4)
def _embedded_catalog(model: str, host: str) -> tuple[tuple[RecipeRecord, ...], tuple[tuple[float, ...], ...]]:
    """Embed the small Phase 1 catalog once per API process and model setting."""
    embedder = _get_embedder(model, host)
    texts = [recipe.search_text for recipe in SEED_RECIPES]
    vectors = embedder.embed_documents(texts)
    return tuple(SEED_RECIPES), tuple(tuple(vector) for vector in vectors)


def _cosine_similarity(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def retrieve_recipes(query: str, *, limit: int = 3) -> list[RecipeMatch]:
    embedder = _get_embedder(config.OLLAMA_EMBED_MODEL, config.OLLAMA_HOST)
    recipes, vectors = _embedded_catalog(config.OLLAMA_EMBED_MODEL, config.OLLAMA_HOST)
    query_vector = embedder.embed_query(query)
    ranked = sorted(
        (
            RecipeMatch(recipe=recipe, score=_cosine_similarity(query_vector, vector))
            for recipe, vector in zip(recipes, vectors, strict=True)
        ),
        key=lambda match: match.score,
        reverse=True,
    )

    # Avoid presenting weak semantic matches as recommendations.
    return [match for match in ranked[:limit] if match.score >= 0.20]


def prepare_recipe_index() -> int:
    recipes, _vectors = _embedded_catalog(config.OLLAMA_EMBED_MODEL, config.OLLAMA_HOST)
    return len(recipes)


def _recipe_context(matches: list[RecipeMatch]) -> str:
    sections = []
    for match in matches:
        recipe = match.recipe
        sections.append(
            "\n".join(
                (
                    f"Recipe: {recipe.title}",
                    f"Preparation time: {recipe.prep_minutes} minutes",
                    f"Description: {recipe.body}",
                    f"Ingredients: {', '.join(recipe.ingredients)}",
                    f"Instructions: {' '.join(recipe.instructions)}",
                )
            )
        )
    return "\n\n---\n\n".join(sections)


def _response_text(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
    return str(content).strip()


def answer_recipe_query(message: str, settings: UserSettings) -> RagAnswer:
    matches = retrieve_recipes(message)
    if not matches:
        return RagAnswer(
            answer=(
                "I couldn't find a close match in this sample recipe collection. "
                "Try naming an ingredient, cuisine, or time limit."
            ),
            recipes=[],
        )

    model = build_chat_model(
        settings.provider,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        ollama_model=settings.ollama_model,
    )
    result = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are Thyme, a helpful recipe finder. Answer using only the "
                    "recipe context provided. Recommend the best matches for the "
                    "user's ingredients, time, and preferences. Do not invent recipes, "
                    "ingredients, preparation times, or instructions. If a request "
                    "cannot be met by the context, say so and offer the closest "
                    "supported option. Keep the answer concise and name the recipes "
                    "you used."
                )
            ),
            HumanMessage(
                content=(
                    f"User request:\n{message}\n\n"
                    f"Retrieved recipe context:\n{_recipe_context(matches)}"
                )
            ),
        ]
    )
    return RagAnswer(answer=_response_text(result), recipes=matches)
