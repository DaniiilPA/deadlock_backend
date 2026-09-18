from typing import Annotated
from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status

from app.api.dependencies import get_auth_service, get_client_ip, get_current_user
from app.core.config import settings
from app.core.security import delete_refresh_cookie, set_refresh_cookie
from app.db.models import User
from app.schemas import (
    AuthResponse,
    MessageResponse,
    TokenRefreshResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserRegisterRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    user_agent: Annotated[str | None, Header()] = None,
):
    result = await auth_service.register_user(
        data=body,
        ip_address=get_client_ip(request),
        user_agent=user_agent,
    )
    set_refresh_cookie(response, result.tokens.refresh_token)

    return AuthResponse(
        access_token=result.tokens.access_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: UserLoginRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    user_agent: Annotated[str | None, Header()] = None,
):
    result = await auth_service.authenticate_user(
        data=body,
        ip_address=get_client_ip(request),
        user_agent=user_agent,
    )
    set_refresh_cookie(response, result.tokens.refresh_token)

    return AuthResponse(
        access_token=result.tokens.access_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie()] = None,
    user_agent: Annotated[str | None, Header()] = None,
):
    try:
        tokens = await auth_service.rotate_refresh_token(
            raw_refresh_token=refresh_token,
            ip_address=get_client_ip(request),
            user_agent=user_agent,
        )
    except Exception:
        delete_refresh_cookie(response)
        raise

    set_refresh_cookie(response, tokens.refresh_token)

    return TokenRefreshResponse(
        access_token=tokens.access_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return UserResponse.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    await auth_service.revoke_session(refresh_token)
    delete_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    await auth_service.revoke_all_sessions(current_user.id)
    delete_refresh_cookie(response)
    return MessageResponse(message="All sessions revoked")