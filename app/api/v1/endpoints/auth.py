from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, RefreshRequest, UserOut
from app.services.auth_service import auth_service
from app.api.v1.dependencies import get_current_user
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Реєстрація нового користувача."""
    user = await auth_service.register(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Авторизація, отримання JWT токенів."""
    return await auth_service.login(db, data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Оновлення access token через refresh token."""
    return await auth_service.refresh(db, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """Дані поточного авторизованого користувача."""
    return current_user
