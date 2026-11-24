"""Shared configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
DATA_DIR = BACKEND_ROOT / "data"

load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")

# Hugging Face: optional auth for model downloads (does not speed local inference)
_hf = os.getenv("HF_TOKEN", "").strip()
if _hf:
    os.environ.setdefault("HF_TOKEN", _hf)
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", _hf)

# local | aws
THYME_ENV = os.getenv("THYME_ENV", "local")
DEFAULT_USER_ID = os.getenv("THYME_DEFAULT_USER_ID", "local-dev")
# When false (default), Cognito Bearer token is required — no anonymous local-dev.
ALLOW_ANON = os.getenv("THYME_ALLOW_ANON", "false").lower() in {"1", "true", "yes"}

# Local laptop testing (same as 590R-AI labs)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Optional Fernet key for encrypting BYOK secrets at rest
THYME_SECRETS_KEY = os.getenv("THYME_SECRETS_KEY", "")

# AWS (filled from Terraform outputs — safe to use in local for Cognito login/admin)
AWS_REGION = os.getenv("AWS_REGION", "us-west-1")
USER_SECRETS_TABLE = os.getenv("USER_SECRETS_TABLE", "thyme-user-secrets")
RECIPES_TABLE = os.getenv("RECIPES_TABLE", "thyme-recipes")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "us-west-1_Oqxx0Qvpk")
COGNITO_APP_CLIENT_ID = os.getenv(
    "COGNITO_APP_CLIENT_ID",
    "3aj94humt4rjn2gu9uklv9sd5j",
)

# Phase 1 RAG — local Chroma + optional Tavily web search
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma")))
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Google Calendar OAuth (Plan page — separate from Cognito)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:8765/api/calendar/google/callback",
).strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/")

