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

# local | aws
THYME_ENV = os.getenv("THYME_ENV", "local")
DEFAULT_USER_ID = os.getenv("THYME_DEFAULT_USER_ID", "local-dev")

# Local laptop testing (same as 590R-AI labs)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# Optional Fernet key for encrypting BYOK secrets at rest
THYME_SECRETS_KEY = os.getenv("THYME_SECRETS_KEY", "")

# AWS (filled from Terraform outputs — safe to use in local for Cognito login/admin)
AWS_REGION = os.getenv("AWS_REGION", "us-west-1")
USER_SECRETS_TABLE = os.getenv("USER_SECRETS_TABLE", "thyme-user-secrets")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "us-west-1_Oqxx0Qvpk")
COGNITO_APP_CLIENT_ID = os.getenv(
    "COGNITO_APP_CLIENT_ID",
    "3aj94humt4rjn2gu9uklv9sd5j",
)

