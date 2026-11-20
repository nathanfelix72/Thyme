"""Recipe upload / storage API stubs.

Next sprint: users upload their own recipes into a DB used as RAG source.
"""

from fastapi import APIRouter

from app.modules.shared.schemas import StubStatus

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


@router.get("", response_model=StubStatus)
def recipes_root() -> StubStatus:
    return StubStatus(
        module="recipes",
        detail="Recipe CRUD / upload endpoints will live here.",
    )


@router.post("/upload", response_model=StubStatus)
def upload_recipe() -> StubStatus:
    # TODO: accept file or JSON → RecipeStore.create → trigger rag indexing
    return StubStatus(
        module="recipes",
        detail="TODO: upload recipe → store in DB → index for RAG.",
    )


@router.get("/list", response_model=StubStatus)
def list_recipes() -> StubStatus:
    return StubStatus(
        module="recipes",
        detail="TODO: list stored recipes.",
    )
