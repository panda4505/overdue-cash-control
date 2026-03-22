from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/occ"

    # LLM
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""

    # Email (Resend)
    RESEND_API_KEY: str = ""
    RESEND_WEBHOOK_SECRET: str = ""

    # Auth
    SECRET_KEY: str = "dev-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # File storage
    UPLOAD_DIR: str = "uploads"

    # Test database — required for running DB tests. Must differ from DATABASE_URL.
    TEST_DATABASE_URL: str = ""

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
