"""Single-shot non-agentic LLM helpers for a recipe (no tools / loops)."""

from __future__ import annotations

from app.modules.recipes.normalize import _invoke_structured
from app.modules.recipes.schemas import (
    Ingredient,
    RecipeAssistInput,
    ScaleServingsOut,
    ScaleServingsResponse,
    SuggestSideOut,
    SuggestSideResponse,
    SummarizeOut,
    SummarizeResponse,
)

_CONTEXT_CHARS = 6000


def _context(recipe: RecipeAssistInput) -> str:
    parts = [f"Title: {recipe.title.strip() or 'Untitled'}"]
    if recipe.servings:
        parts.append(f"Servings: {recipe.servings}")
    if recipe.cuisine:
        parts.append(f"Cuisine: {recipe.cuisine}")
    if recipe.difficulty:
        parts.append(f"Difficulty: {recipe.difficulty}")
    if recipe.ingredients:
        parts.append("Ingredients:")
        for ing in recipe.ingredients[:40]:
            line = " ".join(
                p for p in [ing.quantity, ing.unit, ing.name] if p
            ).strip()
            parts.append(f"- {line}")
    if recipe.steps:
        parts.append("Steps:")
        for i, step in enumerate(recipe.steps[:30], start=1):
            parts.append(f"{i}. {step}")
    body = (recipe.raw_text or "").strip()
    if body:
        parts.append("Recipe text:")
        parts.append(body[:_CONTEXT_CHARS])
    return "\n".join(parts)


def summarize_recipe(user_id: str, recipe: RecipeAssistInput) -> SummarizeResponse:
    prompt = (
        "Summarize this cooking recipe in exactly 1–2 short sentences for a cook. "
        "Focus on what the dish is and the main method. No preamble.\n\n"
        f"{_context(recipe)}"
    )
    out = _invoke_structured(user_id, prompt, SummarizeOut, task="summarize")
    assert isinstance(out, SummarizeOut)
    text = out.summary.strip()
    if not text:
        raise ValueError("Empty summary from model")
    return SummarizeResponse(summary=text)


def suggest_side(user_id: str, recipe: RecipeAssistInput) -> SuggestSideResponse:
    prompt = (
        "Suggest 2–3 simple side dishes that pair well with this main recipe. "
        "Keep each side short (name + one brief why). Stay practical for a home cook.\n\n"
        f"{_context(recipe)}"
    )
    out = _invoke_structured(user_id, prompt, SuggestSideOut, task="suggest_side")
    assert isinstance(out, SuggestSideOut)
    sides = [s.strip() for s in out.sides if s and str(s).strip()][:5]
    if not sides:
        raise ValueError("No side suggestions from model")
    return SuggestSideResponse(sides=sides, notes=(out.notes or "").strip())


def scale_servings(
    user_id: str,
    recipe: RecipeAssistInput,
    *,
    target_servings: int,
) -> ScaleServingsResponse:
    if target_servings < 1 or target_servings > 48:
        raise ValueError("target_servings must be between 1 and 48")
    base = recipe.servings or 4
    prompt = (
        f"Scale this recipe from {base} servings to {target_servings} servings. "
        "Return adjusted ingredient quantities (keep names; update quantity/unit). "
        "If the source has no clear quantities, estimate reasonable ones. "
        "Add a short notes string about any timing/pan-size caveats.\n\n"
        f"{_context(recipe)}"
    )
    out = _invoke_structured(user_id, prompt, ScaleServingsOut, task="scale")
    assert isinstance(out, ScaleServingsOut)
    ingredients = [
        Ingredient(
            name=ing.name.strip()[:120],
            quantity=(ing.quantity.strip()[:40] if ing.quantity else None),
            unit=(ing.unit.strip()[:40] if ing.unit else None),
        )
        for ing in out.ingredients
        if ing.name and ing.name.strip()
    ][:40]
    if not ingredients:
        raise ValueError("No scaled ingredients from model")
    return ScaleServingsResponse(
        target_servings=target_servings,
        ingredients=ingredients,
        notes=(out.notes or "").strip(),
    )
