"""Admin endpoints — Cognito user list + admins group management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.shared import config
from app.modules.shared.auth import AuthUser, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMINS_GROUP = "admins"


class CognitoUserRow(BaseModel):
    username: str
    email: str | None = None
    status: str | None = None
    enabled: bool = True
    created_at: str | None = None
    is_admin: bool = False


class UserListResponse(BaseModel):
    users: list[CognitoUserRow]


class SetAdminRequest(BaseModel):
    is_admin: bool


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if config.THYME_ENV == "local" and user.user_id == config.DEFAULT_USER_ID:
        # Local laptop without Cognito JWT: allow viewing when pool is configured
        if not config.COGNITO_USER_POOL_ID:
            raise HTTPException(status_code=501, detail="Cognito pool not configured")
        return user
    if ADMINS_GROUP not in user.groups:
        raise HTTPException(status_code=403, detail="Admin group required")
    return user


def _cognito():
    import boto3

    return boto3.client("cognito-idp", region_name=config.AWS_REGION)


def _admin_identities(client) -> set[str]:
    """Usernames / subs / emails currently in the admins group."""
    ids: set[str] = set()
    next_token: str | None = None
    while True:
        kwargs: dict = {
            "UserPoolId": config.COGNITO_USER_POOL_ID,
            "GroupName": ADMINS_GROUP,
            "Limit": 60,
        }
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.list_users_in_group(**kwargs)
        for raw in resp.get("Users", []):
            username = raw.get("Username")
            if username:
                ids.add(username)
            attrs = {a["Name"]: a["Value"] for a in raw.get("Attributes", [])}
            for key in ("sub", "email"):
                val = attrs.get(key)
                if val:
                    ids.add(val)
                    ids.add(val.lower())
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return ids


def _row_from_cognito(raw: dict, admin_ids: set[str]) -> CognitoUserRow:
    attrs = {a["Name"]: a["Value"] for a in raw.get("Attributes", [])}
    created = raw.get("UserCreateDate")
    username = raw.get("Username", "")
    email = attrs.get("email")
    sub = attrs.get("sub")
    markers = {username, sub, email, (email or "").lower()}
    return CognitoUserRow(
        username=username,
        email=email,
        status=raw.get("UserStatus"),
        enabled=bool(raw.get("Enabled", True)),
        created_at=created.isoformat() if created else None,
        is_admin=bool(markers & admin_ids),
    )


def _is_self(admin: AuthUser, *, username: str, email: str | None) -> bool:
    markers = {admin.user_id}
    if admin.email:
        markers.add(admin.email)
        markers.add(admin.email.lower())
    targets = {username}
    if email:
        targets.add(email)
        targets.add(email.lower())
    return bool(markers & targets)


@router.get("/users", response_model=UserListResponse)
def list_users(_admin: AuthUser = Depends(require_admin)) -> UserListResponse:
    if not config.COGNITO_USER_POOL_ID:
        raise HTTPException(status_code=501, detail="COGNITO_USER_POOL_ID not set")

    client = _cognito()
    admin_ids = _admin_identities(client)
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
            users.append(_row_from_cognito(raw, admin_ids))
        pagination_token = resp.get("PaginationToken")
        if not pagination_token:
            break

    return UserListResponse(users=users)


@router.put("/users/{username}/admin", response_model=CognitoUserRow)
def set_user_admin(
    username: str,
    body: SetAdminRequest,
    admin: AuthUser = Depends(require_admin),
) -> CognitoUserRow:
    """Add or remove a Cognito user from the admins group."""
    if not config.COGNITO_USER_POOL_ID:
        raise HTTPException(status_code=501, detail="COGNITO_USER_POOL_ID not set")

    from botocore.exceptions import ClientError

    client = _cognito()
    try:
        existing = client.admin_get_user(
            UserPoolId=config.COGNITO_USER_POOL_ID,
            Username=username,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"UserNotFoundException", "ResourceNotFoundException"}:
            raise HTTPException(status_code=404, detail="User not found") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    attrs = {a["Name"]: a["Value"] for a in existing.get("UserAttributes", [])}
    target_email = attrs.get("email")
    if not body.is_admin and _is_self(admin, username=username, email=target_email):
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own admin access.",
        )

    try:
        if body.is_admin:
            client.admin_add_user_to_group(
                UserPoolId=config.COGNITO_USER_POOL_ID,
                Username=username,
                GroupName=ADMINS_GROUP,
            )
        else:
            client.admin_remove_user_from_group(
                UserPoolId=config.COGNITO_USER_POOL_ID,
                Username=username,
                GroupName=ADMINS_GROUP,
            )
        resp = client.admin_get_user(
            UserPoolId=config.COGNITO_USER_POOL_ID,
            Username=username,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"UserNotFoundException", "ResourceNotFoundException"}:
            raise HTTPException(status_code=404, detail="User not found") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface Cognito/IAM errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # admin_get_user shape differs slightly from list_users
    out_attrs = {a["Name"]: a["Value"] for a in resp.get("UserAttributes", [])}
    created = resp.get("UserCreateDate")
    return CognitoUserRow(
        username=resp.get("Username", username),
        email=out_attrs.get("email"),
        status=resp.get("UserStatus"),
        enabled=bool(resp.get("Enabled", True)),
        created_at=created.isoformat() if created else None,
        is_admin=body.is_admin,
    )
