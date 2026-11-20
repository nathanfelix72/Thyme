"""Admin endpoints — list Cognito users (admins group only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.shared import config
from app.modules.shared.auth import AuthUser, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


class CognitoUserRow(BaseModel):
    username: str
    email: str | None = None
    status: str | None = None
    enabled: bool = True
    created_at: str | None = None


class UserListResponse(BaseModel):
    users: list[CognitoUserRow]


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if config.THYME_ENV == "local" and user.user_id == config.DEFAULT_USER_ID:
        # Local laptop without Cognito JWT: allow viewing when pool is configured
        if not config.COGNITO_USER_POOL_ID:
            raise HTTPException(status_code=501, detail="Cognito pool not configured")
        return user
    if "admins" not in user.groups:
        raise HTTPException(status_code=403, detail="Admin group required")
    return user


@router.get("/users", response_model=UserListResponse)
def list_users(_admin: AuthUser = Depends(require_admin)) -> UserListResponse:
    if not config.COGNITO_USER_POOL_ID:
        raise HTTPException(status_code=501, detail="COGNITO_USER_POOL_ID not set")

    import boto3

    client = boto3.client("cognito-idp", region_name=config.AWS_REGION)
    users: list[CognitoUserRow] = []
    pagination_token: str | None = None

    while True:
        kwargs: dict = {
            "UserPoolId": config.COGNITO_USER_POOL_ID,
            "Limit": 60,
        }
        if pagination_token:
            kwargs["PaginationToken"] = pagination_token
        resp = client.list_users(**kwargs)
        for raw in resp.get("Users", []):
            attrs = {a["Name"]: a["Value"] for a in raw.get("Attributes", [])}
            created = raw.get("UserCreateDate")
            users.append(
                CognitoUserRow(
                    username=raw.get("Username", ""),
                    email=attrs.get("email"),
                    status=raw.get("UserStatus"),
                    enabled=bool(raw.get("Enabled", True)),
                    created_at=created.isoformat() if created else None,
                )
            )
        pagination_token = resp.get("PaginationToken")
        if not pagination_token:
            break

    return UserListResponse(users=users)
