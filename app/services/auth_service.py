import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.models import PasswordResetToken, User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserUpdate
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class AuthService:
    async def register(self, db: AsyncSession, data: UserRegister) -> User:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
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
                detail="Invalid email or password",
            )
        if not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        return self._build_tokens(user)

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        user_id = payload.get("sub")
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
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
                    detail="A user with this email already exists",
                )
            user.email = data.email
        if data.name is not None:
            user.name = data.name
        if data.position is not None:
            user.position = data.position
        if data.company is not None:
            user.company = data.company
        if data.password is not None:
            if not data.current_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is required to change the password",
                )
            if not user.password_hash or not verify_password(
                data.current_password, user.password_hash
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect",
                )
            user.password_hash = get_password_hash(data.password)
        await db.flush()
        await db.refresh(user)
        return user

    async def forgot_password(self, db: AsyncSession, email: str) -> None:
        result = await db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        user: Optional[User] = result.scalar_one_or_none()
        if not user:
            return
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        db.add(reset_token)
        await db.flush()
        try:
            await email_service.send_password_reset_email(db, user.id, token)
        except Exception:
            logger.warning("Failed to send password reset email to user %s", user.id)

    async def reset_password(
        self,
        db: AsyncSession,
        token: str,
        new_password: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == token,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        )
        reset_token: Optional[PasswordResetToken] = result.scalar_one_or_none()
        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token",
            )
        result2 = await db.execute(
            select(User).where(User.id == reset_token.user_id)
        )
        user: Optional[User] = result2.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found",
            )
        user.password_hash = get_password_hash(new_password)
        reset_token.used_at = now
        await db.flush()

    def _build_tokens(self, user: User) -> TokenResponse:
        payload = {"sub": str(user.id)}
        return TokenResponse(
            access_token=create_access_token(payload),
            refresh_token=create_refresh_token(payload),
        )


auth_service = AuthService()
