"""App-level Google OAuth client credentials (one-time setup in the UI).

Env vars GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET still win if set.
Otherwise credentials are Fernet-encrypted under backend/data/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from cryptography.fernet import InvalidToken

from app.modules.shared import config
from app.modules.settings.store import _fernet


@dataclass(frozen=True)
class GoogleAppCredentials:
    client_id: str
    client_secret: str


def _cred_path():
    return config.DATA_DIR / "google_oauth_app.json"


def load_stored_credentials() -> GoogleAppCredentials | None:
    path = _cred_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        blob = raw.get("payload")
        if not blob:
            return None
        decrypted = _fernet().decrypt(blob.encode()).decode()
        data = json.loads(decrypted)
        client_id = (data.get("client_id") or "").strip()
        client_secret = (data.get("client_secret") or "").strip()
        if not client_id or not client_secret:
            return None
        return GoogleAppCredentials(client_id=client_id, client_secret=client_secret)
    except (InvalidToken, json.JSONDecodeError, OSError, TypeError):
        return None


def save_stored_credentials(client_id: str, client_secret: str) -> GoogleAppCredentials:
    cid = client_id.strip()
    secret = client_secret.strip()
    if not cid or not secret:
        raise ValueError("client_id and client_secret are required")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"client_id": cid, "client_secret": secret})
    token = _fernet().encrypt(payload.encode()).decode()
    _cred_path().write_text(json.dumps({"payload": token}, indent=2), encoding="utf-8")
    return GoogleAppCredentials(client_id=cid, client_secret=secret)


def clear_stored_credentials() -> None:
    path = _cred_path()
    if path.exists():
        path.unlink()


def resolve_credentials() -> GoogleAppCredentials | None:
    """Prefer process env, then UI-saved credentials."""
    env_id = config.GOOGLE_CLIENT_ID
    env_secret = config.GOOGLE_CLIENT_SECRET
    if env_id and env_secret:
        return GoogleAppCredentials(client_id=env_id, client_secret=env_secret)
    return load_stored_credentials()
