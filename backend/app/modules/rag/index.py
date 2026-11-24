"""Local Chroma index per user for semantic recipe search."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.modules.recipes.schemas import Recipe
from app.modules.shared import config


@lru_cache(maxsize=1)
def _embedding_fn() -> Any:
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    return SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)


def warm_embeddings() -> None:
    """Load MiniLM into memory so the first index/search is not a cold start."""
    fn = _embedding_fn()
    sample = ["thyme embedding warmup"]
    if hasattr(fn, "__call__"):
        fn(sample)
    elif hasattr(fn, "embed_documents"):
        fn.embed_documents(sample)


def _collection(user_id: str) -> Any:
    import chromadb

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
    path = config.CHROMA_DIR / safe
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path))
    return client.get_or_create_collection(
        name="recipes",
        embedding_function=_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def _metadata(recipe: Recipe) -> dict[str, Any]:
    keywords = ", ".join(k.lower() for k in recipe.ingredient_keywords)
    legacy = ", ".join(i.name.lower() for i in recipe.ingredients)
    return {
        "recipe_id": recipe.recipe_id,
        "title": recipe.title[:200],
        "source": recipe.source,
        "difficulty": recipe.difficulty or "",
        "total_time_minutes": int(recipe.total_time_minutes)
        if recipe.total_time_minutes is not None
        else -1,
        "cuisine": (recipe.cuisine or "").lower(),
        "ingredients_text": (keywords or legacy)[:900],
        "tags": ", ".join(t.lower() for t in recipe.tags)[:400],
    }


def index_recipes(user_id: str, recipes: list[Recipe]) -> int:
    if not recipes:
        return 0
    col = _collection(user_id)
    ids = [r.recipe_id for r in recipes]
    documents = [r.embed_text() for r in recipes]
    metadatas = [_metadata(r) for r in recipes]
    # Upsert so re-index after re-upload is safe
    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def index_recipe(user_id: str, recipe: Recipe) -> None:
    index_recipes(user_id, [recipe])


def delete_from_index(user_id: str, recipe_id: str) -> None:
    col = _collection(user_id)
    try:
        col.delete(ids=[recipe_id])
    except Exception:
        # Missing id is fine — recipe may never have been indexed
        pass


def search_recipes(
    user_id: str,
    *,
    query: str,
    n_results: int = 24,
    difficulty: str | None = None,
    cuisine: str | None = None,
) -> list[dict[str, Any]]:
    """Semantic search; optional exact metadata filters for difficulty/cuisine.

    Time and ingredient include/exclude are applied by the search service in Python.
    """
    col = _collection(user_id)
    if col.count() == 0:
        return []

    where: dict[str, Any] | None = None
    clauses: list[dict[str, Any]] = []
    if difficulty:
        clauses.append({"difficulty": difficulty})
    if cuisine:
        clauses.append({"cuisine": cuisine.lower()})
    if len(clauses) == 1:
        where = clauses[0]
    elif len(clauses) > 1:
        where = {"$and": clauses}

    q = (query or "").strip() or "recipe dinner meal"
    fetch = min(max(n_results, 1), max(col.count(), 1))
    kwargs: dict[str, Any] = {
        "query_texts": [q],
        "n_results": fetch,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    try:
        result = col.query(**kwargs)
    except Exception:
        kwargs.pop("where", None)
        result = col.query(**kwargs)

    ids = (result.get("ids") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]

    hits: list[dict[str, Any]] = []
    for i, rid in enumerate(ids):
        dist = dists[i] if i < len(dists) else 1.0
        score = max(0.0, 1.0 - float(dist))
        hits.append(
            {
                "recipe_id": rid,
                "score": score,
                "metadata": metas[i] if i < len(metas) else {},
                "document": docs[i] if i < len(docs) else "",
            }
        )
    return hits
