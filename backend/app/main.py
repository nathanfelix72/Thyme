"""Thyme API entrypoint.

Run from repo root (venv active):
  uvicorn app.main:app --reload --app-dir backend --port 8080
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.shared import config  # noqa: F401  # load .env early
from app.modules.admin.router import router as admin_router
from app.modules.budget.router import router as budget_router
from app.modules.calendar.router import router as calendar_router
from app.modules.rag.router import router as rag_router
from app.modules.recipes.router import router as recipes_router
from app.modules.settings.router import router as settings_router
from app.modules.shop.router import router as shop_router

logger = logging.getLogger("thyme")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        from app.modules.rag.index import warm_embeddings

        warm_embeddings()
        logger.info("embedding model warmed (%s)", config.EMBEDDING_MODEL)
    except Exception as exc:
        logger.warning("embedding warmup skipped: %s", exc)
    yield


app = FastAPI(title="Thyme API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://dv5md9hmzm76i.cloudfront.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_router)
app.include_router(admin_router)
app.include_router(rag_router)
app.include_router(recipes_router)
app.include_router(calendar_router)
app.include_router(shop_router)
app.include_router(budget_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "thyme-api",
        "env": config.THYME_ENV,
        "default_llm": f"ollama:{config.OLLAMA_MODEL}",
    }

