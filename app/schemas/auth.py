from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import UserRoleName, get_user_role_name


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль має містити щонайменше 8 символів")
        if not any(c.isalpha() for c in v):
            raise ValueError("Пароль має містити щонайменше одну літеру")
        if not any(c.isdigit() for c in v):
            raise ValueError("Пароль має містити щонайменше одну цифру")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: Optional[UserRoleName] = None
    created_at: datetime

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, v) -> Optional[UserRoleName]:
        if isinstance(v, int):
            return get_user_role_name(v)
        return v

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
