import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.models import User
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.core.enums import UserRole
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserUpdate
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class AuthService:

    async def register(self, db: AsyncSession, data: UserRegister) -> User:
        # Перевірка унікальності email
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Користувач з таким email вже існує",
            )
        user = User(
            name=data.name,
            email=data.email,
            password_hash=get_password_hash(data.password),
            role=UserRole.USER,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        try:
            await email_service.send_welcome_email(db, user.id)
        except Exception:
            logger.warning("Failed to send welcome email to user %s", user.id)
        return user

    async def login(self, db: AsyncSession, data: UserLogin) -> TokenResponse:
        result = await db.execute(select(User).where(User.email == data.email))
        user: Optional[User] = result.scalar_one_or_none()
        if not user or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невірний email або пароль",
            )
        if not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невірний email або пароль",
            )
        return self._build_tokens(user)

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалідний refresh token",
            )
        user_id = payload.get("sub")
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалідний refresh token")
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return self._build_tokens(user)

    async def update_me(self, db: AsyncSession, user: User, data: UserUpdate) -> User:
        if data.email is not None and data.email != user.email:
            existing = (
                await db.execute(select(User).where(User.email == data.email))
            ).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Користувач з таким email вже існує",
                )
            user.email = data.email
        if data.name is not None:
            user.name = data.name
        await db.flush()
        await db.refresh(user)
        return user

    def _build_tokens(self, user: User) -> TokenResponse:
        payload = {"sub": str(user.id)}
        return TokenResponse(
            access_token=create_access_token(payload),
            refresh_token=create_refresh_token(payload),
        )


auth_service = AuthService()
