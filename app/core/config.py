from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_CV_BUCKET: str = "candidate-cvs"
    CV_SIGNED_URL_EXPIRE_SECONDS: int = 3600

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Anthropic
    # App
    ENVIRONMENT: str = "development"
    BACKEND_CORS_ORIGINS: str = ""
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "CompetencyHub"
    BACKGROUND_JOBS_ENABLED: bool = False
    BACKGROUND_JOBS_POLL_SECONDS: int = 60
    JOB_DERIVED_MIN_COUNT: int = 2
    JOB_DERIVED_MIN_FREQUENCY: float = 0.03

    # Email / Resend
    EMAILS_ENABLED: bool = False
    EMAIL_FROM: Optional[str] = None
    EMAIL_REPLY_TO: Optional[str] = None
    FRONTEND_BASE_URL: Optional[str] = None
    RESEND_API_KEY: Optional[str] = None
    EMAIL_DEADLINE_REMINDER_DAYS: int = 3

    @property
    def cors_origins(self) -> list[str]:
        if self.BACKEND_CORS_ORIGINS.strip():
            return [
                origin.strip().rstrip("/")
                for origin in self.BACKEND_CORS_ORIGINS.split(",")
                if origin.strip()
            ]
        if self.ENVIRONMENT == "development":
            return ["*"]
        return []

    @property
    def frontend_base_url(self) -> Optional[str]:
        if not self.FRONTEND_BASE_URL:
            return None
        value = self.FRONTEND_BASE_URL.strip().rstrip("/")
        return value or None

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
