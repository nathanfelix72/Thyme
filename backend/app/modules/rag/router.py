"""RAG chatbot API stubs.

Next sprint: chat that retrieves from user-uploaded recipes.
LLM calls should go through shared.llm + settings BYOK (see /api/settings).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.shared.auth import get_current_user_id
from app.modules.shared.schemas import StubStatus

router = APIRouter(prefix="/api/rag", tags=["rag"])


class ChatRequest(BaseModel):
    message: str


@router.get("", response_model=StubStatus)
def rag_root() -> StubStatus:
    return StubStatus(
        module="rag",
        detail="RAG chat + retrieval endpoints will live here.",
    )


@router.post("/chat", response_model=StubStatus)
def chat(
    _body: ChatRequest,
    _user_id: str = Depends(get_current_user_id),
) -> StubStatus:
    # TODO: load user settings → build_chat_model → retrieve recipes → answer
    return StubStatus(
        module="rag",
        detail="TODO: retrieve matching recipes and answer in plain language.",
    )


@router.post("/index", response_model=StubStatus)
def index_recipe() -> StubStatus:
    return StubStatus(
        module="rag",
        detail="TODO: embed + index a stored recipe for retrieval.",
    )

