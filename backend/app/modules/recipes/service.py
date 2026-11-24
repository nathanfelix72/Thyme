"""Recipe ingest: extract → segment verbatim → metadata columns → persist → index."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.modules.recipes.extract import extract_text
from app.modules.recipes.normalize import (
    normalize_document,
    recipes_from_web_snippets as normalize_web,
)
from app.modules.recipes.schemas import (
    Recipe,
    RecipeMetadata,
    RecipeSegment,
    RecipeSource,
    RecipeSummary,
)
from app.modules.recipes.store import RecipeStore, get_recipe_store

ProgressFn = Callable[[dict[str, Any]], None] | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _from_segment(
    user_id: str,
    segment: RecipeSegment,
    meta: RecipeMetadata,
    *,
    source: RecipeSource,
    source_doc: str | None = None,
    source_url: str | None = None,
) -> Recipe:
    stamp = _now()
    return Recipe(
        user_id=user_id,
        recipe_id=str(uuid.uuid4()),
        source=source,
        title=segment.title.strip() or "Untitled recipe",
        raw_text=segment.raw_text.strip(),
        difficulty=meta.difficulty,
        total_time_minutes=meta.total_time_minutes,
        servings=meta.servings,
        cuisine=meta.cuisine,
        tags=list(meta.tags),
        ingredient_keywords=list(meta.ingredient_keywords),
        ingredients=list(meta.ingredients),
        steps=list(meta.steps),
        source_url=source_url,
        source_doc=source_doc,
        created_at=stamp,
        updated_at=stamp,
    )


def ingest_upload(
    user_id: str,
    *,
    filename: str,
    data: bytes,
    store: RecipeStore | None = None,
    on_progress: ProgressFn = None,
) -> list[Recipe]:
    """Parse an uploaded file: verbatim segments + metadata columns."""
    store = store or get_recipe_store()
    if on_progress:
        on_progress(
            {
                "stage": "extract",
                "message": f"Extracting text from {filename}…",
                "percent": 5,
            }
        )
    text = extract_text(filename, data)
    if not text.strip():
        return []
    if on_progress:
        on_progress(
            {
                "stage": "extract",
                "message": f"Extracted {len(text):,} characters",
                "percent": 12,
            }
        )

    pairs = normalize_document(
        user_id, text, hint=filename, on_progress=on_progress
    )
    recipes = [
        _from_segment(
            user_id,
            seg,
            meta,
            source="upload",
            source_doc=filename,
        )
        for seg, meta in pairs
    ]
    if on_progress:
        on_progress(
            {
                "stage": "index",
                "message": f"Saving and indexing {len(recipes)} recipes…",
                "found": len(recipes),
                "percent": 92,
            }
        )
    store.put_many(recipes)
    _index_many(user_id, recipes)
    return recipes


def ingest_pasted_text(
    user_id: str,
    text: str,
    *,
    source_doc: str = "paste.txt",
    store: RecipeStore | None = None,
    on_progress: ProgressFn = None,
) -> list[Recipe]:
    store = store or get_recipe_store()
    pairs = normalize_document(
        user_id, text, hint=source_doc, on_progress=on_progress
    )
    recipes = [
        _from_segment(
            user_id,
            seg,
            meta,
            source="upload",
            source_doc=source_doc,
        )
        for seg, meta in pairs
    ]
    store.put_many(recipes)
    _index_many(user_id, recipes)
    return recipes


def recipes_from_web_snippets(
    user_id: str,
    snippets: list[dict[str, str]],
    *,
    on_progress: ProgressFn = None,
) -> list[Recipe]:
    """Build Recipe objects from web snippets without persisting yet."""
    triples = normalize_web(user_id, snippets, on_progress=on_progress)
    return [
        _from_segment(
            user_id,
            seg,
            meta,
            source="web",
            source_url=url,
        )
        for seg, meta, url in triples
    ]


def persist_recipes(
    user_id: str,
    recipes: list[Recipe],
    *,
    store: RecipeStore | None = None,
) -> list[Recipe]:
    if not recipes:
        return []
    store = store or get_recipe_store()
    stamped = []
    for recipe in recipes:
        data = recipe.model_dump()
        data["user_id"] = user_id
        data["source"] = data.get("source") or "web"
        stamped.append(Recipe.model_validate(data))
    store.put_many(stamped)
    _index_many(user_id, stamped)
    return stamped


def import_recipe(
    user_id: str,
    recipe: Recipe,
    *,
    store: RecipeStore | None = None,
) -> Recipe:
    """Persist a preview recipe (typically from web search) into the library."""
    saved = persist_recipes(user_id, [recipe], store=store)
    return saved[0]


def list_summaries(user_id: str, store: RecipeStore | None = None) -> list[RecipeSummary]:
    store = store or get_recipe_store()
    recipes = store.list_for_user(user_id)
    recipes.sort(key=lambda r: r.updated_at, reverse=True)
    return [r.summary() for r in recipes]


def get_recipe(
    user_id: str,
    recipe_id: str,
    store: RecipeStore | None = None,
) -> Recipe | None:
    store = store or get_recipe_store()
    return store.get(user_id, recipe_id)


def delete_recipe(
    user_id: str,
    recipe_id: str,
    store: RecipeStore | None = None,
) -> bool:
    store = store or get_recipe_store()
    deleted = store.delete(user_id, recipe_id)
    if deleted:
        from app.modules.rag.index import delete_from_index

        delete_from_index(user_id, recipe_id)
    return deleted


def _keywords_from_ingredients(
    ingredients: list,
    existing: list[str] | None = None,
) -> list[str]:
    """Prefer structured ingredient names; keep extras from prior keywords."""
    names: list[str] = []
    seen: set[str] = set()
    for item in ingredients:
        name = (
            item.name.strip()
            if hasattr(item, "name")
            else str((item or {}).get("name") or "").strip()
        )
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    for kw in existing or []:
        cleaned = str(kw).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        names.append(cleaned)
    return names[:40]


def update_recipe(
    user_id: str,
    recipe_id: str,
    updates: dict[str, Any],
    *,
    store: RecipeStore | None = None,
) -> Recipe | None:
    """Apply a partial update, persist, and reindex for search."""
    store = store or get_recipe_store()
    existing = store.get(user_id, recipe_id)
    if not existing:
        return None

    data = existing.model_dump()
    for key, value in updates.items():
        if key in {
            "recipe_id",
            "user_id",
            "source",
            "created_at",
            "updated_at",
            "source_doc",
        }:
            continue
        data[key] = value

    if "tags" in updates:
        data["tags"] = [
            str(t).strip() for t in (data.get("tags") or []) if t and str(t).strip()
        ][:24]

    if "steps" in updates:
        data["steps"] = [
            str(s).strip() for s in (data.get("steps") or []) if s and str(s).strip()
        ][:80]

    if "ingredients" in updates:
        cleaned_ings = []
        for item in data.get("ingredients") or []:
            payload = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            name = str(payload.get("name") or "").strip()
            if not name:
                continue
            cleaned_ings.append(
                {
                    "name": name[:120],
                    "quantity": (
                        str(payload["quantity"]).strip()[:40]
                        if payload.get("quantity")
                        else None
                    ),
                    "unit": (
                        str(payload["unit"]).strip()[:40]
                        if payload.get("unit")
                        else None
                    ),
                }
            )
        data["ingredients"] = cleaned_ings[:60]
        if "ingredient_keywords" not in updates and cleaned_ings:
            data["ingredient_keywords"] = _keywords_from_ingredients(
                cleaned_ings, None
            )

    if "ingredient_keywords" in updates:
        data["ingredient_keywords"] = [
            str(k).strip()
            for k in (data.get("ingredient_keywords") or [])
            if k and str(k).strip()
        ][:40]

    title = str(data.get("title") or "").strip() or "Untitled recipe"
    data["title"] = title[:200]
    if data.get("cuisine") is not None:
        cuisine = str(data.get("cuisine") or "").strip()
        data["cuisine"] = cuisine[:80] or None
    if data.get("raw_text") is not None:
        data["raw_text"] = str(data.get("raw_text") or "")

    data["recipe_id"] = existing.recipe_id
    data["user_id"] = user_id
    data["source"] = existing.source
    data["created_at"] = existing.created_at
    data["source_doc"] = existing.source_doc
    data["updated_at"] = _now()

    recipe = Recipe.model_validate(data)
    store.put(recipe)
    from app.modules.rag.index import index_recipe

    index_recipe(user_id, recipe)
    return recipe


def _index_many(user_id: str, recipes: list[Recipe]) -> None:
    from app.modules.rag.index import index_recipes

    index_recipes(user_id, recipes)
