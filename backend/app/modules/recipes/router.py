"""Recipe upload / storage API."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.modules.recipes.helpers import scale_servings, suggest_side, summarize_recipe
from app.modules.recipes.schemas import (
    Recipe,
    RecipeAssistInput,
    RecipeListResponse,
    RecipeUpdate,
    ScaleServingsRequest,
    ScaleServingsResponse,
    SuggestSideResponse,
    SummarizeResponse,
    UploadResponse,
)
from app.modules.recipes.service import (
    delete_recipe,
    get_recipe,
    import_recipe,
    ingest_pasted_text,
    ingest_upload,
    list_summaries,
    update_recipe,
)
from app.modules.shared.auth import get_current_user_id
from app.modules.shared.schemas import StubStatus

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


class PasteRequest(BaseModel):
    text: str
    source_doc: str = "paste.txt"


@router.get("", response_model=StubStatus)
def recipes_root() -> StubStatus:
    return StubStatus(
        module="recipes",
        detail="Upload PDF/TXT, list, and fetch normalized recipes.",
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_recipe(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
) -> UploadResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    filename = file.filename or "upload.bin"
    try:
        recipes = ingest_upload(user_id, filename=filename, data=data)
    except Exception as exc:  # noqa: BLE001 — surface LLM/parse errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResponse(
        uploaded=len(recipes),
        recipes=[r.summary() for r in recipes],
    )


@router.post("/upload-progress")
async def upload_recipe_progress(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    """Stream NDJSON progress events while normalizing an upload."""
    import queue
    import threading

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    filename = file.filename or "upload.bin"

    def event_stream() -> Iterator[str]:
        events: queue.Queue[dict | None] = queue.Queue()

        def on_progress(event: dict) -> None:
            events.put(event)

        def worker() -> None:
            try:
                events.put(
                    {
                        "stage": "start",
                        "message": f"Starting upload of {filename}…",
                        "percent": 1,
                    }
                )
                recipes = ingest_upload(
                    user_id,
                    filename=filename,
                    data=data,
                    on_progress=on_progress,
                )
                events.put(
                    {
                        "stage": "done",
                        "uploaded": len(recipes),
                        "found": len(recipes),
                        "percent": 100,
                        "message": f"Done — parsed {len(recipes)} recipes",
                        "recipes": [r.summary().model_dump() for r in recipes],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                events.put(
                    {
                        "stage": "error",
                        "message": str(exc),
                        "percent": 100,
                    }
                )
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = events.get()
            if item is None:
                break
            yield json.dumps(item, default=str) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/paste", response_model=UploadResponse)
def paste_recipe(
    body: PasteRequest,
    user_id: str = Depends(get_current_user_id),
) -> UploadResponse:
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    try:
        recipes = ingest_pasted_text(
            user_id,
            body.text,
            source_doc=body.source_doc,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResponse(
        uploaded=len(recipes),
        recipes=[r.summary() for r in recipes],
    )


@router.get("/list", response_model=RecipeListResponse)
def list_recipes(
    user_id: str = Depends(get_current_user_id),
) -> RecipeListResponse:
    return RecipeListResponse(recipes=list_summaries(user_id))


@router.post("/import", response_model=Recipe)
def import_preview_recipe(
    recipe: Recipe,
    user_id: str = Depends(get_current_user_id),
) -> Recipe:
    """Save a web/search preview into the user's library (explicit opt-in)."""
    try:
        return import_recipe(user_id, recipe)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assist/summarize", response_model=SummarizeResponse)
def assist_summarize(
    body: RecipeAssistInput,
    user_id: str = Depends(get_current_user_id),
) -> SummarizeResponse:
    """One-shot: 1–2 sentence recipe summary (no tools)."""
    try:
        return summarize_recipe(user_id, body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assist/suggest-side", response_model=SuggestSideResponse)
def assist_suggest_side(
    body: RecipeAssistInput,
    user_id: str = Depends(get_current_user_id),
) -> SuggestSideResponse:
    """One-shot: suggest simple side dishes (no tools)."""
    try:
        return suggest_side(user_id, body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assist/scale", response_model=ScaleServingsResponse)
def assist_scale(
    body: ScaleServingsRequest,
    user_id: str = Depends(get_current_user_id),
) -> ScaleServingsResponse:
    """One-shot: scale ingredient quantities to target servings (no tools)."""
    try:
        return scale_servings(
            user_id,
            body,
            target_servings=body.target_servings,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{recipe_id}", response_model=Recipe)
def fetch_recipe(
    recipe_id: str,
    user_id: str = Depends(get_current_user_id),
) -> Recipe:
    recipe = get_recipe(user_id, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.put("/{recipe_id}", response_model=Recipe)
def put_recipe(
    recipe_id: str,
    body: RecipeUpdate,
    user_id: str = Depends(get_current_user_id),
) -> Recipe:
    """Update a library recipe and reindex embeddings for search."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        recipe = get_recipe(user_id, recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return recipe
    try:
        recipe = update_recipe(user_id, recipe_id, updates)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.delete("/{recipe_id}")
def remove_recipe(
    recipe_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, bool | str]:
    if not delete_recipe(user_id, recipe_id):
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {"deleted": True, "recipe_id": recipe_id}
