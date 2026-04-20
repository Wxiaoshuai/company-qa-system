from fastapi import Cookie, Depends, HTTPException, Request

from app.core.auth_store import AuthError, UserRecord, auth_store
from app.core.config import settings


def user_to_dict(user: UserRecord) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is None:
        return None
    return request.client.host


def get_optional_current_user(
    session_token: str | None = Cookie(default=None, alias=settings.auth_session_cookie_name),
) -> UserRecord | None:
    return auth_store.get_user_by_session_token(session_token)


def get_current_user(user: UserRecord | None = Depends(get_optional_current_user)) -> UserRecord:
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录。")
    return user


def require_admin(user: UserRecord = Depends(get_current_user)) -> UserRecord:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="没有管理员权限。")
    return user


def ensure_role_value(role: str) -> str:
    normalized = (role or "user").strip().lower()
    if normalized not in {"user", "admin"}:
        raise AuthError("角色只支持 user 或 admin。")
    return normalized
