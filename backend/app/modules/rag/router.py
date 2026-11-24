"""Filter-driven recipe search API (non-agentic)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.rag.schemas import (
    IndexRequest,
    IndexResponse,
    SearchRequest,
    SearchResponse,
)
from app.modules.rag.service import reindex_recipe, search
from app.modules.shared.auth import get_current_user_id
from app.modules.shared.schemas import StubStatus

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("", response_model=StubStatus)
def rag_root() -> StubStatus:
    return StubStatus(
        module="rag",
        detail="Filter + semantic recipe search (POST /api/rag/search).",
    )


@router.post("/search", response_model=SearchResponse)
def search_recipes(
    body: SearchRequest,
    user_id: str = Depends(get_current_user_id),
) -> SearchResponse:
    try:
        return search(user_id, body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/index", response_model=IndexResponse)
def index_one(
    body: IndexRequest,
    user_id: str = Depends(get_current_user_id),
) -> IndexResponse:
    ok = reindex_recipe(user_id, body.recipe_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return IndexResponse(indexed=True, recipe_id=body.recipe_id)
