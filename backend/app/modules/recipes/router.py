"""Recipe upload / storage API.

/upload runs Intelligent Document Analysis (see extraction.py), saves the
structured recipe for the current user, and returns it. RAG indexing is TODO.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.modules.recipes.extraction import (
    UnsupportedFileError,
    extract_recipe,
    extract_text,
)
from app.modules.recipes.schemas import ExtractionResult
from app.modules.recipes.service import StoredRecipe, get_recipe_store
from app.modules.recipes.web import UrlFetchError, recipe_text_from_url
from app.modules.settings.store import get_store
from app.modules.shared.auth import get_current_user_id
from app.modules.shared.llm import build_chat_model

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/upload", response_model=ExtractionResult)
async def upload_recipe(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    url: str | None = Form(default=None),
    user_id: str = Depends(get_current_user_id),
) -> ExtractionResult:
    """Import a recipe from exactly one of: a file (PDF / .txt), pasted text, or a web page URL."""
    text = text if text and text.strip() else None
    url = url.strip() if url and url.strip() else None
    # Swagger UI / browsers can send an empty file part when no file is picked
    data = await file.read() if file is not None else b""
    if not data:
        file = None

    received = [name for name, v in (("file", file), ("text", text), ("url", url)) if v is not None]
    if len(received) != 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide exactly one of: file, text, or url "
                f"(received: {', '.join(received) or 'none'})."
            ),
        )

    filename: str | None = None
    source_url: str | None = None
    if file is not None:
        filename = file.filename
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File is larger than 10 MB.")
        try:
            source = extract_text(file.filename or "", file.content_type, data)
        except UnsupportedFileError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        source_type = "file"
    elif url is not None:
        try:
            # Blocking network I/O -> run off the event loop
            source_url, source, method = await run_in_threadpool(recipe_text_from_url, url)
        except UrlFetchError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        source_type = f"url_{method}"
    else:
        source = text
        source_type = "text"

    settings = get_store().get(user_id)
    try:
        model = build_chat_model(
            settings.provider,
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            ollama_model=settings.ollama_model,
            temperature=0,
        )
        recipe, attempts = await run_in_threadpool(extract_recipe, source, model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stored = get_recipe_store().create(
        user_id, recipe, source_filename=filename, source_url=source_url
    )
    # TODO: trigger rag indexing for stored.id
    return ExtractionResult(
        id=stored.id,
        recipe=recipe,
        source=source_type,
        attempts=attempts,
        source_chars=len(source),
    )


@router.get("/list", response_model=list[StoredRecipe])
def list_recipes(user_id: str = Depends(get_current_user_id)) -> list[StoredRecipe]:
    """All of the current user's saved recipes, newest first."""
    return get_recipe_store().list_all(user_id)


@router.get("/{recipe_id}", response_model=StoredRecipe)
def get_recipe(recipe_id: str, user_id: str = Depends(get_current_user_id)) -> StoredRecipe:
    stored = get_recipe_store().get(user_id, recipe_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return stored


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: str, user_id: str = Depends(get_current_user_id)) -> None:
    if not get_recipe_store().delete(user_id, recipe_id):
        raise HTTPException(status_code=404, detail="Recipe not found.")
