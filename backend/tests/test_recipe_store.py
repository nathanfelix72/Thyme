"""Local recipe store persistence tests."""

from __future__ import annotations

from app.modules.recipes.schemas import Ingredient, Recipe
from app.modules.recipes.store import LocalRecipeStore


def _recipe(user_id: str, recipe_id: str, title: str) -> Recipe:
    return Recipe(
        user_id=user_id,
        recipe_id=recipe_id,
        source="upload",
        title=title,
        ingredients=[Ingredient(name="salt")],
        steps=["Mix"],
        difficulty="easy",
        total_time_minutes=15,
        raw_text=title,
        source_doc="test.txt",
    )


def test_local_store_put_get_list(tmp_data):
    store = LocalRecipeStore(root=tmp_data / "recipes")
    r1 = _recipe("u1", "a", "Soup")
    r2 = _recipe("u1", "b", "Salad")
    store.put_many([r1, r2])

    assert store.get("u1", "a").title == "Soup"
    titles = {r.title for r in store.list_for_user("u1")}
    assert titles == {"Soup", "Salad"}
    assert store.get("u1", "missing") is None
    assert store.list_for_user("other") == []
    assert store.delete("u1", "a") is True
    assert store.get("u1", "a") is None
    assert store.delete("u1", "a") is False
