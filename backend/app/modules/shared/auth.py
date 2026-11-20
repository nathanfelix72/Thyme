"""Request identity helpers.

Local: X-User-Id header or default local-dev (no Cognito required for laptop AI).
When Authorization Bearer is present, verify Cognito JWT and use that identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from urllib.request import urlopen

from fastapi import Depends, Header, HTTPException, Request
from jose import JWTError, jwt

from app.modules.shared import config


@dataclass
class AuthUser:
    user_id: str
    email: str | None = None
    groups: list[str] = field(default_factory=list)
    token: str | None = None


@lru_cache(maxsize=4)
def _jwks(user_pool_id: str, region: str) -> dict[str, Any]:
    url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    with urlopen(url, timeout=10) as resp:  # noqa: S310 — fixed AWS Cognito URL
        return json.loads(resp.read().decode())


def _verify_cognito_token(token: str) -> AuthUser:
    if not config.COGNITO_USER_POOL_ID or not config.COGNITO_APP_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Cognito is not configured on the API")

    region = config.AWS_REGION
    pool = config.COGNITO_USER_POOL_ID
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool}"
    jwks = _jwks(pool, region)

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Unknown token signing key")

        # Access tokens use `client_id` instead of `aud` — verify manually.
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False, "verify_at_hash": False},
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    token_use = claims.get("token_use")
    client = config.COGNITO_APP_CLIENT_ID
    if token_use == "id":
        if claims.get("aud") != client:
            raise HTTPException(status_code=401, detail="Token audience mismatch")
    elif token_use == "access":
        if claims.get("client_id") != client:
            raise HTTPException(status_code=401, detail="Token client mismatch")
    else:
        raise HTTPException(status_code=401, detail="Unexpected token use")

    # Groups are on the access token; email is on the id token.
    groups = claims.get("cognito:groups") or []
    if isinstance(groups, str):
        groups = [groups]

    return AuthUser(
        user_id=str(claims.get("sub") or ""),
        email=claims.get("email"),
        groups=list(groups),
        token=token,
    )



def get_current_user(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AuthUser:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return _verify_cognito_token(auth.removeprefix("Bearer ").strip())

    if config.THYME_ENV == "local":
        uid = (x_user_id or config.DEFAULT_USER_ID).strip() or config.DEFAULT_USER_ID
        return AuthUser(user_id=uid, email=None, groups=[])

    raise HTTPException(status_code=401, detail="Missing Cognito bearer token")


def get_current_user_id(user: AuthUser = Depends(get_current_user)) -> str:
    return user.user_id
