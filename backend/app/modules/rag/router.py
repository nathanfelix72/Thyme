"""Semantic recipe search API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.rag.service import answer_recipe_query, prepare_recipe_index
from app.modules.recipes.catalog import SEED_RECIPES
from app.modules.settings.store import get_store
from app.modules.shared.auth import get_current_user_id

router = APIRouter(prefix="/api/rag", tags=["rag"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)


class RecipeSource(BaseModel):
    id: str
    title: str
    description: str
    prep_minutes: int
    ingredients: list[str]
    instructions: list[str]
    tags: list[str]
    relevance: float


class ChatResponse(BaseModel):
    answer: str
    recipes: list[RecipeSource]


class IndexResponse(BaseModel):
    indexed_recipes: int
    embedding_model: str


@router.get("")
def rag_root() -> dict[str, str | int]:
    return {
        "module": "rag",
        "detail": "Semantic search over the Phase 1 sample recipe collection.",
        "sample_recipes": len(SEED_RECIPES),
    }


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
) -> ChatResponse:
    settings = get_store().get(user_id)
    try:
        result = answer_recipe_query(body.message.strip(), settings)
    except Exception as exc:  # noqa: BLE001 — return actionable local setup errors
        raise HTTPException(
            status_code=503,
            detail=(
                "Recipe search is unavailable. Check that Ollama is running and "
                "that its embedding model is installed. "
                f"Details: {exc}"
            ),
        ) from exc

    recipes = [
        RecipeSource(
            id=match.recipe.id,
            title=match.recipe.title,
            description=match.recipe.body,
            prep_minutes=match.recipe.prep_minutes,
            ingredients=list(match.recipe.ingredients),
            instructions=list(match.recipe.instructions),
            tags=list(match.recipe.tags),
            relevance=round(match.score, 3),
        )
        for match in result.recipes
    ]
    return ChatResponse(answer=result.answer, recipes=recipes)


@router.post("/index", response_model=IndexResponse)
def index_recipes() -> IndexResponse:
    """Warm the in-memory vector index for the bundled sample recipes."""
    try:
        count = prepare_recipe_index()
    except Exception as exc:  # noqa: BLE001 — return actionable local setup errors
        raise HTTPException(
            status_code=503,
            detail=f"Could not build recipe index. Check Ollama setup. Details: {exc}",
        ) from exc
    from app.modules.shared import config

    return IndexResponse(
        indexed_recipes=count,
        embedding_model=config.OLLAMA_EMBED_MODEL,
    )
