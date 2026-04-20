from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.auth import ensure_role_value, get_client_ip, get_current_user, require_admin, user_to_dict
from app.core.auth_store import AuthError, UserRecord, auth_store
from app.core.config import settings
from app.models.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    UserCreateRequest,
    UserPasswordResetRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])


def _set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=max(1, settings.auth_session_ttl_hours) * 3600,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.auth_session_cookie_name, path="/")


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    try:
        user = auth_store.authenticate(payload.username, payload.password, ip_address=get_client_ip(request))
        session_token = auth_store.create_session(user.id)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    _set_session_cookie(response, session_token)
    return LoginResponse(user=UserResponse(**user_to_dict(user)))


@router.post("/auth/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    current_user: UserRecord = Depends(get_current_user),
) -> MessageResponse:
    session_token = request.cookies.get(settings.auth_session_cookie_name)
    auth_store.invalidate_session(session_token, user_id=current_user.id, ip_address=get_client_ip(request))
    _clear_session_cookie(response)
    return MessageResponse(message="已退出登录。")


@router.get("/auth/me", response_model=UserResponse)
def current_user_info(current_user: UserRecord = Depends(get_current_user)) -> UserResponse:
    return UserResponse(**user_to_dict(current_user))


@router.get("/admin/users", response_model=list[UserResponse])
def list_users(_: UserRecord = Depends(require_admin)) -> list[UserResponse]:
    return [UserResponse(**user_to_dict(user)) for user in auth_store.list_users()]


@router.post("/admin/users", response_model=UserResponse)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    admin_user: UserRecord = Depends(require_admin),
) -> UserResponse:
    try:
        user = auth_store.create_user(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            role=ensure_role_value(payload.role),
            is_active=payload.is_active,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="用户名已存在。") from exc
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    auth_store.log_event(
        "user_created",
        user_id=admin_user.id,
        target_user_id=user.id,
        detail=f"role={user.role}",
        ip_address=get_client_ip(request),
    )
    return UserResponse(**user_to_dict(user))


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    admin_user: UserRecord = Depends(require_admin),
) -> UserResponse:
    try:
        user = auth_store.update_user(
            user_id=user_id,
            role=ensure_role_value(payload.role) if payload.role is not None else None,
            is_active=payload.is_active,
            display_name=payload.display_name,
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    auth_store.log_event(
        "user_updated",
        user_id=admin_user.id,
        target_user_id=user.id,
        detail=f"role={user.role},active={user.is_active}",
        ip_address=get_client_ip(request),
    )
    return UserResponse(**user_to_dict(user))


@router.post("/admin/users/{user_id}/reset-password", response_model=MessageResponse)
def reset_password(
    user_id: int,
    payload: UserPasswordResetRequest,
    request: Request,
    admin_user: UserRecord = Depends(require_admin),
) -> MessageResponse:
    try:
        user = auth_store.update_user(user_id=user_id, password=payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    auth_store.log_event(
        "password_reset",
        user_id=admin_user.id,
        target_user_id=user.id,
        ip_address=get_client_ip(request),
    )
    return MessageResponse(message="密码已重置。")
