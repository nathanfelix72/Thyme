"""Single-shot recipe assist helpers (mocked LLM)."""

from __future__ import annotations

from app.modules.recipes.schemas import (
    Ingredient,
    ScaleServingsOut,
    SuggestSideOut,
    SummarizeOut,
)


def _payload():
    return {
        "title": "Garlic Pasta",
        "raw_text": "Garlic Pasta\n2 cups pasta\n4 cloves garlic\nBoil and toss.",
        "ingredients": [
            {"name": "pasta", "quantity": "2", "unit": "cups"},
            {"name": "garlic", "quantity": "4", "unit": "cloves"},
        ],
        "steps": ["Boil pasta.", "Toss with garlic."],
        "servings": 4,
        "cuisine": "italian",
        "difficulty": "easy",
    }


def test_assist_summarize(client, monkeypatch):
    monkeypatch.setattr(
        "app.modules.recipes.helpers._invoke_structured",
        lambda *a, **k: SummarizeOut(
            summary="A quick garlic pasta tossed in olive oil."
        ),
    )
    res = client.post("/api/recipes/assist/summarize", json=_payload())
    assert res.status_code == 200
    assert "garlic" in res.json()["summary"].lower()


def test_assist_suggest_side(client, monkeypatch):
    monkeypatch.setattr(
        "app.modules.recipes.helpers._invoke_structured",
        lambda *a, **k: SuggestSideOut(
            sides=["Simple green salad", "Garlic bread"],
            notes="Keep sides light.",
        ),
    )
    res = client.post("/api/recipes/assist/suggest-side", json=_payload())
    assert res.status_code == 200
    body = res.json()
    assert len(body["sides"]) == 2
    assert "salad" in body["sides"][0].lower()


def test_assist_scale(client, monkeypatch):
    monkeypatch.setattr(
        "app.modules.recipes.helpers._invoke_structured",
        lambda *a, **k: ScaleServingsOut(
            ingredients=[
                Ingredient(name="pasta", quantity="4", unit="cups"),
                Ingredient(name="garlic", quantity="8", unit="cloves"),
            ],
            notes="Use a larger pot.",
        ),
    )
    body = {**_payload(), "target_servings": 8}
    res = client.post("/api/recipes/assist/scale", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["target_servings"] == 8
    assert data["ingredients"][0]["quantity"] == "4"
    assert "larger" in data["notes"].lower()


def test_assist_scale_rejects_bad_target(client, monkeypatch):
    monkeypatch.setattr(
        "app.modules.recipes.helpers._invoke_structured",
        lambda *a, **k: ScaleServingsOut(ingredients=[]),
    )
    body = {**_payload(), "target_servings": 0}
    res = client.post("/api/recipes/assist/scale", json=body)
    assert res.status_code == 422
