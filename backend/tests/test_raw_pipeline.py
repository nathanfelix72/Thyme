"""Tests for heuristic/hint segmentation + rule metadata (minimal LLM)."""

from __future__ import annotations

from app.modules.recipes.normalize import (
    clean_web_snippet,
    enrich_metadata,
    heuristic_segments,
    metadata_from_rules,
    normalize_document,
    segment_document,
    slice_segments_from_locators,
)
from app.modules.recipes.schemas import RecipeLocator, RecipeMetadata, RecipeSegment


def test_heuristic_segments_splits_blank_line_recipes():
    source = (
        "Tomato Soup\n\nIngredients:\n2 cups tomatoes\n\nSteps:\nSimmer 20 minutes.\n\n"
        "Garlic Bread\n\nToast bread with garlic butter."
    )
    segs = heuristic_segments(source)
    assert len(segs) >= 2
    assert any("tomato" in s.raw_text.lower() for s in segs)
    assert all("cups of fresh ripe" not in s.raw_text for s in segs)


def test_slice_segments_from_hints_is_verbatim():
    source = (
        "Tomato Soup\n\nIngredients:\n2 cups tomatoes\n\nSteps:\nSimmer.\n\n"
        "Garlic Bread\n\nToast bread with garlic butter."
    )
    locs = [
        RecipeLocator(title="Tomato Soup", start_hint="Tomato Soup"),
        RecipeLocator(title="Garlic Bread", start_hint="Garlic Bread"),
    ]
    pairs = slice_segments_from_locators(source, locs)
    assert len(pairs) == 2
    _, soup = pairs[0]
    assert "2 cups tomatoes" in soup.raw_text
    assert "Garlic Bread" not in soup.raw_text


def test_segment_uses_heuristic_without_llm(monkeypatch):
    source = (
        "Tomato Soup\n\nIngredients:\n2 cups tomatoes\n\nSteps:\nSimmer.\n\n"
        "Garlic Bread\n\nToast bread with garlic butter."
    )
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise RuntimeError("should not call LLM")

    monkeypatch.setattr("app.modules.recipes.normalize._invoke_json", boom)
    segs = segment_document("u1", source)
    assert called["n"] == 0
    assert len(segs) >= 2


def test_rule_metadata_keywords_and_time():
    seg = RecipeSegment(
        title="Lemon Chicken",
        raw_text="Easy lemon chicken with garlic. Cook 25 minutes. Serves 4.",
    )
    meta = metadata_from_rules(seg)
    assert meta.difficulty == "easy"
    assert meta.total_time_minutes == 25
    assert meta.servings == 4
    assert "chicken" in meta.ingredient_keywords
    assert "lemon" in meta.ingredient_keywords
    assert "garlic" in meta.ingredient_keywords


def test_enrich_metadata_no_llm(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no llm")

    monkeypatch.setattr("app.modules.recipes.normalize._invoke_json", boom)
    seg = RecipeSegment(
        title="Pasta",
        raw_text="Pasta with tomato, basil, olive oil. Boil 10 minutes.",
    )
    meta = enrich_metadata("u1", seg)
    assert "tomato" in meta.ingredient_keywords
    assert meta.total_time_minutes == 10


def test_normalize_document_pairs(monkeypatch):
    source = "Simple Salad\n\nLettuce and vinegar."
    monkeypatch.setattr(
        "app.modules.recipes.normalize._invoke_json",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no")),
    )
    events: list[dict] = []
    pairs = normalize_document("u1", source, on_progress=events.append)
    assert len(pairs) >= 1
    seg, meta = pairs[0]
    assert "Lettuce" in seg.raw_text or "lettuce" in seg.raw_text.lower()
    assert isinstance(meta, RecipeMetadata)
    assert "segment" in [e.get("stage") for e in events]


def test_fallback_single_segment_when_empty_heuristic(monkeypatch):
    monkeypatch.setattr(
        "app.modules.recipes.normalize.heuristic_segments",
        lambda text: [],
    )
    monkeypatch.setattr(
        "app.modules.recipes.normalize._invoke_json",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    text = "One Recipe\n\nJust dump everything in a pan."
    pairs = normalize_document("u1", text, hint="one.txt")
    assert len(pairs) == 1
    assert pairs[0][0].raw_text == text


def test_clean_web_snippet_keeps_ingredients_and_steps(monkeypatch):
    from app.modules.recipes.schemas import WebRecipeClean

    def fake_structured(user_id, prompt, schema, **kwargs):
        assert schema is WebRecipeClean
        return WebRecipeClean(
            title="Roasted Grapes and Rice",
            ingredients=[
                {"name": "rice", "quantity": "1", "unit": "cup"},
                {"name": "grapes", "quantity": "2", "unit": "cups"},
            ],
            steps=["Roast the grapes.", "Cook the rice.", "Combine and serve."],
            difficulty="easy",
            total_time_minutes=35,
            servings=4,
            cuisine="american",
            ingredient_keywords=["rice", "grapes"],
        )

    monkeypatch.setattr(
        "app.modules.recipes.normalize._invoke_structured", fake_structured
    )
    noisy = (
        "Share on Facebook Subscribe now Related Recipes Ad: buy pans\n"
        "Roasted Grapes and Rice\n1 cup rice\n2 cups grapes\nRoast then combine.\n"
        "Leave a comment Star rating 4.8 Equipment: blender"
    )
    cleaned = clean_web_snippet(
        "u1",
        title="Roasted Grapes and Rice - Blog",
        content=noisy,
        source_url="https://example.com/recipe",
    )
    assert cleaned is not None
    seg, meta = cleaned
    assert "Ingredients" in seg.raw_text
    assert "Instructions" in seg.raw_text
    assert "Share on Facebook" not in seg.raw_text
    assert "Leave a comment" not in seg.raw_text
    assert len(meta.ingredients) == 2
    assert len(meta.steps) == 3
    assert meta.difficulty == "easy"
    assert meta.total_time_minutes == 35


def test_clean_web_snippet_skips_non_recipe(monkeypatch):
    from app.modules.recipes.schemas import WebRecipeClean

    monkeypatch.setattr(
        "app.modules.recipes.normalize._invoke_structured",
        lambda *a, **k: WebRecipeClean(
            title="Not a recipe",
            ingredients=[],
            steps=[],
        ),
    )
    assert (
        clean_web_snippet("u1", title="Home", content="Welcome to our blog") is None
    )


def test_invoke_structured_retries_then_json_fallback(monkeypatch):
    from app.modules.recipes.normalize import _invoke_structured
    from app.modules.recipes.schemas import WebRecipeClean

    class BoomModel:
        def with_structured_output(self, schema):
            class Failing:
                def invoke(self, prompt):
                    raise ValueError("bad shape")

            return Failing()

    monkeypatch.setattr(
        "app.modules.recipes.normalize._user_model", lambda user_id: BoomModel()
    )
    monkeypatch.setattr(
        "app.modules.recipes.normalize._invoke_json",
        lambda *a, **k: {
            "title": "Fallback Soup",
            "ingredients": [{"name": "broth"}],
            "steps": ["Heat."],
            "difficulty": "easy",
            "total_time_minutes": 10,
            "servings": 2,
            "cuisine": "general",
            "ingredient_keywords": ["broth"],
        },
    )
    result = _invoke_structured("u1", "prompt", WebRecipeClean, max_retries=2)
    assert isinstance(result, WebRecipeClean)
    assert result.title == "Fallback Soup"
