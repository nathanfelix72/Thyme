"""Filter + embedding similarity search over library; optional web previews."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Callable

from app.modules.rag.index import index_recipe, search_recipes
from app.modules.rag.schemas import SearchHit, SearchRequest, SearchResponse
from app.modules.rag.web_search import build_web_query, tavily_search
from app.modules.recipes.schemas import Recipe
from app.modules.recipes.service import (
    get_recipe,
    recipes_from_web_snippets,
)
from app.modules.recipes.store import get_recipe_store
from app.modules.settings.store import get_store

ProgressFn = Callable[[dict[str, Any]], None] | None

_FUZZY_RATIO = 0.78


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum() or ch.isspace()).strip()


def _fuzzy_in_blob(needle: str, blob: str) -> bool:
    if not needle:
        return True
    if needle in blob:
        return True
    # Token-level fuzzy against words in blob
    words = blob.split()
    for w in words:
        if len(w) < 3:
            continue
        if needle in w or w in needle:
            return True
        if SequenceMatcher(None, needle, w).ratio() >= _FUZZY_RATIO:
            return True
    return False


def _passes_ingredient_filters(
    recipe: Recipe,
    include: list[str],
    exclude: list[str],
) -> bool:
    blob = recipe.filter_blob()
    for item in include:
        if not _fuzzy_in_blob(_norm(item), blob):
            return False
    for item in exclude:
        if _fuzzy_in_blob(_norm(item), blob):
            return False
    return True


def _merge_excludes(user_id: str, request_excludes: list[str]) -> list[str]:
    always = get_store().get(user_id).always_exclude_ingredients or []
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*always, *request_excludes]:
        key = _norm(item)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item.strip())
    return merged


def _passes_time(recipe: Recipe, max_time: int | None) -> bool:
    if max_time is None:
        return True
    if recipe.total_time_minutes is None:
        return True
    return recipe.total_time_minutes <= max_time


def _passes_tags(recipe: Recipe, tags: list[str]) -> bool:
    if not tags:
        return True
    have = {_norm(t) for t in recipe.tags}
    blob = recipe.filter_blob()
    for t in tags:
        n = _norm(t)
        if not n:
            continue
        if n in have or n in blob:
            continue
        return False
    return True


def _build_semantic_query(req: SearchRequest) -> str:
    if req.query and req.query.strip():
        return req.query.strip()
    parts: list[str] = []
    parts.extend(req.include_ingredients)
    if req.cuisine:
        parts.append(req.cuisine)
    if req.difficulty:
        parts.append(req.difficulty)
    parts.extend(req.tags)
    if req.max_time_minutes is not None:
        parts.append(f"{req.max_time_minutes} minute meal")
    return " ".join(parts) if parts else "recipe dinner"


def _reason(recipe: Recipe, score: float, origin: str) -> str:
    bits: list[str] = []
    bits.append("from web search" if origin == "web" else "from your library")
    if recipe.difficulty:
        bits.append(recipe.difficulty)
    if recipe.total_time_minutes is not None:
        bits.append(f"{recipe.total_time_minutes} min")
    bits.append(f"match {score:.0%}")
    return " · ".join(bits)


def _reject_reason(
    recipe: Recipe,
    include: list[str],
    exclude: list[str],
    max_time: int | None,
) -> str | None:
    blob = recipe.filter_blob()
    for item in include:
        if not _fuzzy_in_blob(_norm(item), blob):
            return f"missing “{item}”"
    for item in exclude:
        if _fuzzy_in_blob(_norm(item), blob):
            return f"contains “{item}”"
    if max_time is not None and recipe.total_time_minutes is not None:
        if recipe.total_time_minutes > max_time:
            return f"takes {recipe.total_time_minutes} min (max {max_time})"
    return None


def search(
    user_id: str,
    req: SearchRequest,
    *,
    on_progress: ProgressFn = None,
) -> SearchResponse:
    """Library: embed retrieve → hard filters → similarity ranking.
    Web (opt-in): preview-only; never writes to the library.
    """

    def progress(event: dict[str, Any]) -> None:
        if on_progress:
            on_progress(event)

    store = get_recipe_store()
    excludes = _merge_excludes(user_id, req.exclude_ingredients)
    semantic_q = _build_semantic_query(req)
    local_results: list[SearchHit] = []
    seen: set[str] = set()
    activity: list[dict[str, Any]] = []

    def note(event: dict[str, Any]) -> None:
        activity.append(event)
        progress(event)

    if req.include_library:
        note(
            {
                "stage": "library",
                "message": f"Embedding search over library (query: {semantic_q!r})…",
            }
        )
        hits = search_recipes(
            user_id,
            query=semantic_q,
            n_results=max(req.limit * 3, 24),
            difficulty=req.difficulty,
            cuisine=req.cuisine,
        )
        for hit in hits:
            recipe = store.get(user_id, hit["recipe_id"])
            if not recipe:
                continue
            why = _reject_reason(
                recipe, req.include_ingredients, excludes, req.max_time_minutes
            )
            if why or not _passes_tags(recipe, req.tags):
                note(
                    {
                        "stage": "filter",
                        "message": f"Rejected “{recipe.title}” — {why or 'tag mismatch'}",
                        "rejected": True,
                        "title": recipe.title,
                    }
                )
                continue
            seen.add(recipe.recipe_id)
            local_results.append(
                SearchHit(
                    recipe=recipe,
                    score=float(hit["score"]),
                    reason=_reason(recipe, float(hit["score"]), "local"),
                    origin="local",
                )
            )
        local_results = sorted(
            local_results, key=lambda h: h.score, reverse=True
        )[: req.limit]
        note(
            {
                "stage": "library",
                "message": f"Library matches: {len(local_results)}",
                "found": len(local_results),
            }
        )

    web_queried = False
    web_query: str | None = None
    web_previews = 0
    web_results: list[SearchHit] = []

    if req.include_web:
        web_query = build_web_query(
            query=req.query,
            include_ingredients=req.include_ingredients,
            exclude_ingredients=excludes,
            max_time_minutes=req.max_time_minutes,
            difficulty=req.difficulty,
            cuisine=req.cuisine,
        )
        note(
            {
                "stage": "web",
                "message": f"Tavily search: {web_query}",
                "web_query": web_query,
            }
        )
        snippets = tavily_search(web_query, max_results=max(req.limit, 6))
        web_queried = True
        note(
            {
                "stage": "web",
                "message": f"Tavily returned {len(snippets)} hit(s)",
                "hits": [
                    {"title": s.get("title"), "url": s.get("url")} for s in snippets
                ],
            }
        )
        if snippets:
            # Build in-memory Recipe objects only — never persist here.
            candidates = recipes_from_web_snippets(
                user_id, snippets, on_progress=progress
            )
            for recipe in candidates:
                why = _reject_reason(
                    recipe, req.include_ingredients, excludes, req.max_time_minutes
                )
                if why or not _passes_tags(recipe, req.tags):
                    note(
                        {
                            "stage": "filter",
                            "message": f"Rejected web “{recipe.title}” — {why or 'tag mismatch'}",
                            "rejected": True,
                            "title": recipe.title,
                        }
                    )
                    continue
                if recipe.recipe_id in seen:
                    continue
                score = max(0.4, 0.92 - len(web_results) * 0.07)
                seen.add(recipe.recipe_id)
                web_results.append(
                    SearchHit(
                        recipe=recipe,
                        score=score,
                        reason=_reason(recipe, score, "web"),
                        origin="web",
                    )
                )
            web_previews = len(web_results)
            note(
                {
                    "stage": "web",
                    "message": (
                        f"{web_previews} preview(s) only — "
                        "NOT saved to library until you click Add"
                    ),
                    "found": web_previews,
                    "saved": 0,
                }
            )

    if req.include_web and not req.include_library:
        merged = web_results[: req.limit]
    elif req.include_library and not req.include_web:
        merged = local_results[: req.limit]
    else:
        merged = sorted(
            local_results + web_results,
            key=lambda h: h.score,
            reverse=True,
        )[: req.limit]

    return SearchResponse(
        results=merged,
        web_queried=web_queried,
        web_query=web_query,
        web_imported=0,
        web_previews=web_previews,
        activity=activity,
    )


def reindex_recipe(user_id: str, recipe_id: str) -> bool:
    recipe = get_recipe(user_id, recipe_id)
    if not recipe:
        return False
    index_recipe(user_id, recipe)
    return True
