"""Signed OAuth state binding a Cognito user_id to the Google callback."""

from __future__ import annotations

import json
import time
import uuid

from cryptography.fernet import InvalidToken

from app.modules.settings.store import _fernet

_STATE_TTL_SECONDS = 600


def encode_oauth_state(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": int(time.time()) + _STATE_TTL_SECONDS,
        "nonce": uuid.uuid4().hex,
    }
    return _fernet().encrypt(json.dumps(payload).encode()).decode()


def decode_oauth_state(state: str) -> str:
    """Return user_id or raise ValueError if invalid/expired."""
    try:
        raw = _fernet().decrypt(state.encode()).decode()
        payload = json.loads(raw)
    except (InvalidToken, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Invalid OAuth state") from exc

    user_id = payload.get("user_id")
    exp = payload.get("exp")
    if not user_id or not isinstance(exp, int):
        raise ValueError("Invalid OAuth state payload")
    if int(time.time()) > exp:
        raise ValueError("OAuth state expired")
    return str(user_id)
