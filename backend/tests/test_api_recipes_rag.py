"""API-level tests with LLM/Chroma/Tavily mocked."""

from __future__ import annotations

from app.modules.recipes.schemas import Recipe, RecipeMetadata, RecipeSegment


def _pair(title: str, raw: str, **meta_kw):
    return (
        RecipeSegment(title=title, raw_text=raw),
        RecipeMetadata(**meta_kw),
    )


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_recipes_empty(client):
    res = client.get("/api/recipes/list")
    assert res.status_code == 200
    assert res.json() == {"recipes": []}


def test_paste_empty_rejected(client):
    res = client.post("/api/recipes/paste", json={"text": "   "})
    assert res.status_code == 400


def test_paste_and_list(client, monkeypatch):
    pairs = [
        _pair(
            "Garlic Pasta",
            "Garlic Pasta\ngarlic, pasta\nBoil and toss.",
            difficulty="easy",
            total_time_minutes=20,
            ingredient_keywords=["garlic", "pasta"],
        )
    ]
    monkeypatch.setattr(
        "app.modules.recipes.service.normalize_document",
        lambda *a, **k: pairs,
    )
    monkeypatch.setattr(
        "app.modules.recipes.service._index_many",
        lambda *a, **k: None,
    )

    res = client.post(
        "/api/recipes/paste",
        json={"text": "Garlic Pasta\ngarlic, pasta\nBoil and toss.", "source_doc": "x.txt"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["uploaded"] == 1
    assert body["recipes"][0]["title"] == "Garlic Pasta"
    assert "garlic" in body["recipes"][0]["ingredient_keywords"]

    listed = client.get("/api/recipes/list")
    assert listed.status_code == 200
    assert len(listed.json()["recipes"]) == 1

    recipe_id = body["recipes"][0]["recipe_id"]
    got = client.get(f"/api/recipes/{recipe_id}")
    assert got.status_code == 200
    assert got.json()["raw_text"].startswith("Garlic Pasta")


def test_update_recipe_reindexes(client, monkeypatch):
    pairs = [
        _pair(
            "Garlic Pasta",
            "Garlic Pasta\ngarlic, pasta\nBoil and toss.",
            difficulty="easy",
            total_time_minutes=20,
            ingredient_keywords=["garlic", "pasta"],
            ingredients=[
                {"name": "garlic", "quantity": "4", "unit": "cloves"},
                {"name": "pasta", "quantity": "2", "unit": "cups"},
            ],
            steps=["Boil pasta.", "Toss with garlic."],
        )
    ]
    monkeypatch.setattr(
        "app.modules.recipes.service.normalize_document",
        lambda *a, **k: pairs,
    )
    monkeypatch.setattr(
        "app.modules.recipes.service._index_many",
        lambda *a, **k: None,
    )
    indexed: list[str] = []

    def fake_index(user_id, recipe):
        indexed.append(recipe.recipe_id)

    monkeypatch.setattr(
        "app.modules.rag.index.index_recipe",
        fake_index,
    )

    created = client.post(
        "/api/recipes/paste",
        json={"text": "Garlic Pasta\ngarlic, pasta\nBoil and toss."},
    )
    assert created.status_code == 200
    recipe_id = created.json()["recipes"][0]["recipe_id"]

    res = client.put(
        f"/api/recipes/{recipe_id}",
        json={
            "title": "Spicy Garlic Pasta",
            "total_time_minutes": 25,
            "ingredients": [
                {"name": "garlic", "quantity": "6", "unit": "cloves"},
                {"name": "pasta", "quantity": "3", "unit": "cups"},
                {"name": "chili flakes", "quantity": "1", "unit": "tsp"},
            ],
            "steps": ["Boil pasta.", "Toast chili.", "Toss with garlic."],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Spicy Garlic Pasta"
    assert body["total_time_minutes"] == 25
    assert len(body["ingredients"]) == 3
    assert "chili flakes" in body["ingredient_keywords"]
    assert indexed == [recipe_id]

    missing = client.put("/api/recipes/does-not-exist", json={"title": "Nope"})
    assert missing.status_code == 404


def test_upload_txt(client, monkeypatch):
    pairs = [_pair("Soup", "Soup\nonion\nSimmer", ingredient_keywords=["onion"])]
    monkeypatch.setattr(
        "app.modules.recipes.service.normalize_document",
        lambda *a, **k: pairs,
    )
    monkeypatch.setattr(
        "app.modules.recipes.service._index_many",
        lambda *a, **k: None,
    )

    res = client.post(
        "/api/recipes/upload",
        files={"file": ("soup.txt", b"Soup\nonion\nSimmer", "text/plain")},
    )
    assert res.status_code == 200
    assert res.json()["uploaded"] == 1


def test_search_local_only(client, monkeypatch, tmp_data):
    from app.modules.recipes.store import LocalRecipeStore
    from app.modules.rag import service as rag_service

    store = LocalRecipeStore(root=tmp_data / "recipes")
    recipe = Recipe(
        user_id="local-dev",
        recipe_id="rid-1",
        source="upload",
        title="Lemon Chicken",
        raw_text="Lemon chicken with lemon juice and chicken thighs",
        ingredient_keywords=["chicken", "lemon"],
        difficulty="easy",
        total_time_minutes=30,
    )
    store.put(recipe)

    monkeypatch.setattr(rag_service, "get_recipe_store", lambda: store)
    monkeypatch.setattr(
        rag_service,
        "search_recipes",
        lambda *a, **k: [
            {"recipe_id": "rid-1", "score": 0.91, "metadata": {}, "document": ""}
        ],
    )

    res = client.post(
        "/api/rag/search",
        json={
            "include_ingredients": ["chicken"],
            "exclude_ingredients": ["peanut"],
            "include_web": False,
            "limit": 5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["web_queried"] is False
    assert len(data["results"]) == 1
    assert data["results"][0]["recipe"]["title"] == "Lemon Chicken"
    assert any(a.get("stage") == "library" for a in data.get("activity", []))


def test_web_only_returns_previews_without_saving(client, monkeypatch, tmp_data):
    from app.modules.recipes.store import LocalRecipeStore
    from app.modules.rag import service as rag_service

    store = LocalRecipeStore(root=tmp_data / "recipes")
    good = Recipe(
        user_id="local-dev",
        recipe_id="web-good",
        source="web",
        title="Chicken Rice Bowl",
        raw_text="Chicken and rice bowl with soy sauce",
        ingredient_keywords=["chicken", "rice"],
        difficulty="easy",
        total_time_minutes=25,
    )
    bad = Recipe(
        user_id="local-dev",
        recipe_id="web-bad",
        source="web",
        title="Chicken Mushrooms",
        raw_text="Chicken with mushrooms, no rice",
        ingredient_keywords=["chicken", "mushrooms"],
    )

    monkeypatch.setattr(rag_service, "get_recipe_store", lambda: store)
    monkeypatch.setattr(rag_service, "tavily_search", lambda *a, **k: [{"title": "x"}])
    monkeypatch.setattr(
        rag_service,
        "recipes_from_web_snippets",
        lambda *a, **k: [bad, good],
    )

    res = client.post(
        "/api/rag/search",
        json={
            "include_library": False,
            "include_web": True,
            "include_ingredients": ["chicken", "rice"],
            "exclude_ingredients": ["mushrooms"],
            "limit": 5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["web_imported"] == 0
    assert data["web_previews"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["recipe"]["title"] == "Chicken Rice Bowl"
    assert store.list_for_user("local-dev") == []


def test_import_web_preview(client, monkeypatch, tmp_data):
    from app.modules.recipes.store import LocalRecipeStore
    from app.modules.recipes import service as recipe_service

    store = LocalRecipeStore(root=tmp_data / "recipes")
    monkeypatch.setattr(recipe_service, "get_recipe_store", lambda: store)
    monkeypatch.setattr(recipe_service, "_index_many", lambda *a, **k: None)

    payload = {
        "user_id": "local-dev",
        "recipe_id": "web-preview-1",
        "source": "web",
        "title": "Web Soup",
        "raw_text": "Web Soup\nstock, onion\nSimmer.",
        "difficulty": "easy",
        "total_time_minutes": 20,
        "servings": 4,
        "cuisine": "general",
        "ingredient_keywords": ["onion", "stock"],
        "ingredients": [{"name": "onion", "quantity": "1", "unit": None}],
        "steps": ["Simmer until soft."],
    }
    res = client.post("/api/recipes/import", json=payload)
    assert res.status_code == 200
    assert res.json()["title"] == "Web Soup"
    assert store.get("local-dev", "web-preview-1") is not None


def test_search_skips_library_when_disabled(client, monkeypatch, tmp_data):
    from app.modules.recipes.store import LocalRecipeStore
    from app.modules.rag import service as rag_service

    store = LocalRecipeStore(root=tmp_data / "recipes")
    store.put(
        Recipe(
            user_id="local-dev",
            recipe_id="rid-lib",
            source="upload",
            title="Library Only",
            raw_text="beans and rice",
        )
    )
    monkeypatch.setattr(rag_service, "get_recipe_store", lambda: store)
    called = {"chroma": False}

    def fake_search(*a, **k):
        called["chroma"] = True
        return [{"recipe_id": "rid-lib", "score": 0.9, "metadata": {}, "document": ""}]

    monkeypatch.setattr(rag_service, "search_recipes", fake_search)
    monkeypatch.setattr(rag_service, "tavily_search", lambda *a, **k: [])

    res = client.post(
        "/api/rag/search",
        json={"include_library": False, "include_web": True, "limit": 5},
    )
    assert res.status_code == 200
    assert called["chroma"] is False
    assert res.json()["results"] == []


def test_delete_recipe(client, monkeypatch):
    pairs = [_pair("Temp Dish", "Temp Dish\nsalt\nMix")]
    monkeypatch.setattr(
        "app.modules.recipes.service.normalize_document",
        lambda *a, **k: pairs,
    )
    monkeypatch.setattr(
        "app.modules.recipes.service._index_many",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.modules.rag.index.delete_from_index",
        lambda *a, **k: None,
    )

    created = client.post(
        "/api/recipes/paste",
        json={"text": "Temp Dish\nsalt\nMix"},
    )
    assert created.status_code == 200
    recipe_id = created.json()["recipes"][0]["recipe_id"]

    deleted = client.delete(f"/api/recipes/{recipe_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/recipes/{recipe_id}").status_code == 404


def test_search_excludes_ingredient(client, monkeypatch, tmp_data):
    from app.modules.recipes.store import LocalRecipeStore
    from app.modules.rag import service as rag_service

    store = LocalRecipeStore(root=tmp_data / "recipes")
    store.put(
        Recipe(
            user_id="local-dev",
            recipe_id="rid-2",
            source="upload",
            title="Peanut Noodles",
            raw_text="Peanut butter noodles with peanut sauce",
            ingredient_keywords=["peanut", "noodles"],
        )
    )
    monkeypatch.setattr(rag_service, "get_recipe_store", lambda: store)
    monkeypatch.setattr(
        rag_service,
        "search_recipes",
        lambda *a, **k: [
            {"recipe_id": "rid-2", "score": 0.8, "metadata": {}, "document": ""}
        ],
    )

    res = client.post(
        "/api/rag/search",
        json={
            "exclude_ingredients": ["peanut"],
            "include_web": False,
        },
    )
    assert res.status_code == 200
    assert res.json()["results"] == []
