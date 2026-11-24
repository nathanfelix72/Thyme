"""Unit tests for search filter helpers (no Chroma/LLM)."""

from __future__ import annotations

from app.modules.rag.service import (
    _passes_ingredient_filters,
    _passes_tags,
    _passes_time,
    _build_semantic_query,
)
from app.modules.rag.schemas import SearchRequest
from app.modules.rag.web_search import build_web_query
from app.modules.recipes.schemas import Recipe


def _recipe(**kwargs) -> Recipe:
    base = dict(
        user_id="u",
        recipe_id="r1",
        source="upload",
        title="Test",
        raw_text="chicken breast and rice with garlic",
        ingredient_keywords=["chicken breast", "rice"],
    )
    base.update(kwargs)
    return Recipe(**base)


def test_include_and_exclude_ingredients():
    recipe = _recipe()
    assert _passes_ingredient_filters(recipe, ["chicken"], [])
    assert not _passes_ingredient_filters(recipe, ["shrimp"], [])
    assert not _passes_ingredient_filters(recipe, [], ["rice"])
    assert _passes_ingredient_filters(recipe, ["chicken"], ["peanut"])


def test_fuzzy_misspelling_include():
    recipe = _recipe()
    assert _passes_ingredient_filters(recipe, ["chiken"], [])


def test_match_against_raw_text_without_keywords():
    recipe = _recipe(
        ingredient_keywords=[],
        raw_text="A stew with lentils, carrots, and thyme.",
    )
    assert _passes_ingredient_filters(recipe, ["lentils"], [])
    assert not _passes_ingredient_filters(recipe, [], ["lentils"])


def test_time_filter_allows_unknown():
    assert _passes_time(_recipe(total_time_minutes=20), 30)
    assert not _passes_time(_recipe(total_time_minutes=45), 30)
    assert _passes_time(_recipe(total_time_minutes=None), 30)


def test_tags_filter():
    recipe = _recipe(tags=["weeknight", "family"])
    assert _passes_tags(recipe, ["weeknight"])
    assert not _passes_tags(recipe, ["dessert"])


def test_semantic_query_from_filters():
    req = SearchRequest(
        include_ingredients=["lemon"],
        cuisine="italian",
        difficulty="easy",
        max_time_minutes=25,
    )
    q = _build_semantic_query(req)
    assert "lemon" in q
    assert "italian" in q
    assert "easy" in q


def test_web_query_builder():
    q = build_web_query(
        query="comfort",
        include_ingredients=["potato"],
        exclude_ingredients=["shellfish"],
        max_time_minutes=40,
        difficulty="medium",
        cuisine=None,
    )
    assert "recipe" in q
    assert "potato" in q
    assert "with potato" in q
    assert "comfort" in q
    assert "-shellfish" in q
    assert "without shellfish" in q
    assert "40" in q
