from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, RefreshRequest, UserOut, UserUpdate, ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth_service import auth_service
from app.api.v1.dependencies import get_current_user
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit(settings.AUTH_REGISTER_RATE_LIMIT)
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Реєстрація нового користувача."""
    user = await auth_service.register(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT)
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Авторизація, отримання JWT токенів."""
    return await auth_service.login(db, data)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.AUTH_REFRESH_RATE_LIMIT)
async def refresh(request: Request, data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Оновлення access token через refresh token."""
    return await auth_service.refresh(db, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Дані поточного авторизованого користувача."""
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Оновлення імені та/або email поточного користувача."""
    return await auth_service.update_me(db, current_user, data)


@router.post("/forgot-password", status_code=200)
@limiter.limit(settings.AUTH_FORGOT_PASSWORD_RATE_LIMIT)
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Запит на скидання пароля."""
    await auth_service.forgot_password(db, data.email)
    return {"message": "Якщо email існує в системі, лист буде надіслано"}


@router.post("/reset-password", status_code=200)
@limiter.limit(settings.AUTH_RESET_PASSWORD_RATE_LIMIT)
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Скидання пароля за токеном."""
    await auth_service.reset_password(db, data.token, data.password)
    return {"message": "Пароль успішно змінено"}
