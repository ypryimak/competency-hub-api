from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.models import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
    UserUpdate,
)
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit(settings.AUTH_REGISTER_RATE_LIMIT)
async def register(
    request: Request,
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    return await auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return JWT tokens."""
    return await auth_service.login(db, data)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.AUTH_REFRESH_RATE_LIMIT)
async def refresh(
    request: Request,
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh the access token using a refresh token."""
    return await auth_service.refresh(db, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user."""
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    return await auth_service.update_me(db, current_user, data)


@router.post("/forgot-password", response_model=MessageResponse, status_code=200)
@limiter.limit(settings.AUTH_FORGOT_PASSWORD_RATE_LIMIT)
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email."""
    await auth_service.forgot_password(db, data.email)
    return {"message": "If the email exists in the system, a reset email will be sent"}


@router.post("/reset-password", response_model=MessageResponse, status_code=200)
@limiter.limit(settings.AUTH_RESET_PASSWORD_RATE_LIMIT)
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset the password using a reset token."""
    await auth_service.reset_password(db, data.token, data.password)
    return {"message": "Password was successfully changed"}
