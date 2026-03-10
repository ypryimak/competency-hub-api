from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: Optional[str] = None
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
    PROJECT_NAME: str = "CompetencyHub API"
    BACKGROUND_JOBS_ENABLED: bool = False
    BACKGROUND_JOBS_POLL_SECONDS: int = 60

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

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
